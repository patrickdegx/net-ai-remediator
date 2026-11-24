import json
import logging
import re
from typing import Any, Dict, Optional

import requests

logger = logging.getLogger("AIAnalyzer")


class NetworkAIAnalyzer:
    """
    Motor de análise inteligente usando Ollama, suporte a Contexto Histórico (RAG)
    e validação de comandos em múltiplas camadas.
    """

    # 1. Palavras/termos destrutivos bloqueados
    COMANDOS_PROIBIDOS = [
        "reload",
        "format",
        "erase",
        "delete",
        "rm ",
        "shutdown",
        "write erase",
        "copy ",
        "redirect",
    ]

    # 2. Operadores de encadeamento/injeção bloqueados diretamente
    # (O '|' é tratado via regex para permitir apenas filtros seguros de leitura no IOS)
    OPERADORES_PROIBIDOS = [";", "&&", "||", "`", "$(", "\n", "\r"]

    # 3. Regex para filtros '|' seguros no Cisco IOS (include, exclude, begin, section)
    _PIPE_SEGURO_RE = re.compile(r"\|\s*(include|exclude|begin|section)(?:\s|$)", re.IGNORECASE)

    # 4. Allowlist: o comando deve começar com um prefixo seguro
    PREFIXOS_PERMITIDOS = (
        "show ",
        "ping ",
        "traceroute ",
        "clear ip bgp ",
        "clear counters ",
    )

    def __init__(
        self,
        modelo: str = "llama3",
        ollama_url: str = "http://localhost:11434/api/generate",
    ):
        self.modelo = modelo
        url_limpa = (ollama_url or "http://localhost:11434/api/generate").strip().rstrip("/")
        if not url_limpa.endswith("/api/generate"):
            url_limpa = f"{url_limpa}/api/generate"
        self.ollama_url = url_limpa
        logger.info(
            f"AI Analyzer inicializado com o modelo '{self.modelo}' (Ollama), "
            f"url='{self.ollama_url}', suporte a RAG e validação de comandos ativa."
        )

    def analisar_log_rede(
        self,
        log_bruto: str,
        equipamento: str,
        historico_recente: Optional[list] = None,
    ) -> Dict[str, Any]:
        """
        Envia o log para a IA junto com o histórico de incidentes recentes (RAG)
        e valida a segurança do comando de remediação retornado.
        """
        if historico_recente and len(historico_recente) > 0:
            linhas_historico = "\n".join(
                [
                    f"- Incidente anterior: [{item.get('status')}] {item.get('diagnostico')} "
                    f"(ID: {item.get('incidente_id')})"
                    for item in historico_recente
                ]
            )
            contexto_historico_str = (
                f"\nHISTÓRICO RECENTE DESTE EQUIPAMENTO NAS ÚLTIMAS HORAS:\n{linhas_historico}\n"
            )
        else:
            contexto_historico_str = (
                "\nHISTÓRICO RECENTE: Nenhum incidente anterior registrado recentemente (Primeiro evento).\n"
            )

        prompt = f"""
        Você é um Engenheiro Sênior de Redes e DevOps especialista em correlação de falhas.
        {contexto_historico_str}
        Analise o log de erro atual abaixo do equipamento '{equipamento}' e retorne APENAS um objeto JSON válido (sem markdown, sem crases ```json) com exatamente estas chaves:
        - "diagnostico": Explicação técnica clara e direta da causa raiz. Considere o histórico acima para detectar se é um problema recorrente (ex: flap intermitente).
        - "severidade": "BAIXA", "MEDIA", "ALTA" ou "CRITICA".
        - "comando_remediacao": Um comando CLI seguro para mitigar o problema.

        LOG ATUAL DO EQUIPAMENTO:
        {log_bruto}
        """

        payload = {
            "model": self.modelo,
            "prompt": prompt,
            "stream": False,
            "format": "json",
            "options": {
                "temperature": 0.0,
            },
        }

        try:
            logger.info(f"Enviando log do equipamento {equipamento} com contexto RAG para a IA...")
            response = requests.post(self.ollama_url, json=payload, timeout=90)

            if response.status_code != 200:
                logger.error(f"Erro na API do Ollama: Status {response.status_code}")
                return self._fallback_resposta(log_bruto)

            resposta_json = response.json()
            texto_gerado = resposta_json.get("response", "{}")
            diagnostico_dict = json.loads(texto_gerado)

            comando_sugerido = diagnostico_dict.get("comando_remediacao", "")
            if not self._validar_comando_seguro(comando_sugerido):
                logger.warning(f"ALERTA DE SEGURANÇA: Comando bloqueado: '{comando_sugerido}'")
                diagnostico_dict["comando_remediacao"] = "show logging"
                diagnostico_dict["diagnostico"] = (
                    diagnostico_dict.get("diagnostico", "")
                    + " [Aviso: Remediação restrita por política de segurança]."
                ).strip()

            logger.info("Análise com RAG concluída e validada com sucesso.")
            return diagnostico_dict

        except requests.exceptions.ConnectionError:
            logger.warning("Ollama não está rodando localmente. Usando fallback.")
            return self._fallback_resposta(log_bruto)
        except Exception as e:
            logger.error(f"Erro inesperado ao consultar a IA: {e}")
            return self._fallback_resposta(log_bruto)

    def _validar_pipe_seguro(self, comando_limpo: str) -> bool:
        """
        Se houver '|', permite apenas filtros seguros de leitura (include, exclude, begin, section).
        Qualquer outro uso de '|' é bloqueado.
        """
        if "|" not in comando_limpo:
            return True

        total_pipes = comando_limpo.count("|")
        pipes_validos = len(self._PIPE_SEGURO_RE.findall(comando_limpo))
        return total_pipes > 0 and total_pipes == pipes_validos

    def _validar_comando_seguro(self, comando: str) -> bool:
        """
        Validação em camadas:
        1) Bloqueia operadores de injeção/encadeamento e valida filtros '|' seguros.
        2) Bloqueia comandos destrutivos.
        3) Exige prefixo explícito da Allowlist.
        """
        if not comando or not isinstance(comando, str):
            return False

        comando_limpo = comando.strip().lower()

        for op in self.OPERADORES_PROIBIDOS:
            if op in comando_limpo:
                logger.warning(f"BLINDAGEM ATIVA: Operador proibido '{op}' detectado em: '{comando}'")
                return False

        if not self._validar_pipe_seguro(comando_limpo):
            logger.warning(f"BLINDAGEM ATIVA: Uso de pipe '|' não autorizado em: '{comando}'")
            return False

        for perigoso in self.COMANDOS_PROIBIDOS:
            if perigoso in comando_limpo:
                logger.warning(f"BLINDAGEM ATIVA: Termo destrutivo '{perigoso}' detectado em: '{comando}'")
                return False

        if not comando_limpo.startswith(self.PREFIXOS_PERMITIDOS):
            logger.warning(f"BLINDAGEM ATIVA: Prefixo não autorizado em: '{comando}'")
            return False

        return True

    def _fallback_resposta(self, log_bruto: str) -> Dict[str, Any]:
        return {
            "diagnostico": f"Análise offline de segurança com histórico. Log: {log_bruto[:60]}...",
            "severidade": "MEDIA",
            "comando_remediacao": "show logging",
        }