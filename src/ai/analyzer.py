import os
import json
import logging
from typing import Dict, Any, Optional
import requests

logger = logging.getLogger("AIAnalyzer")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s - %(message)s")


class NetworkAIAnalyzer:
    """
    Motor de análise inteligente com Strategy Pattern, Whitelist flexível
    e Blacklist de Segurança contra comandos destrutivos.
    """

    # Comandos absolutamente proibidos que a IA JAMAIS pode mandar para um roteador
    COMANDOS_PROIBIDOS = [
        "reload",
        "format",
        "erase",
        "delete",
        "rm ",
        "shutdown",
        "write erase"
    ]

    def __init__(self, modelo: str = "llama3", ollama_url: str = "http://localhost:11434/api/generate"):
        self.modelo = modelo
        self.ollama_url = ollama_url
        logger.info(f"AI Analyzer inicializado com o modelo '{self.modelo}' (Ollama) e suporte a RAG.")

    def analisar_log_rede(self, log_bruto: str, equipamento: str, historico_recente: Optional[list] = None) -> Dict[str, Any]:
        """
        Envia o log para a IA junto com o histórico de incidentes recentes recuperados do DynamoDB (RAG).
        """
        # Monta a string de contexto histórico, se houver registros anteriores
        contexto_historico_str = ""
        if historico_recente and len(historico_recente) > 0:
            contexto_historico_str = "\n".join(
                [f"- Incidente anterior: [{item.get('status')}] {item.get('diagnostico')} (ID: {item.get('incidente_id')})" 
                 for item in historico_recente]
            )
            contexto_historico_str = f"\nHISTÓRICO RECENTE DESTE EQUIPAMENTO NAS ÚLTIMAS HORAS:\n{contexto_historico_str}\n"
        else:
            contexto_historico_str = "\nHISTÓRICO RECENTE: Nenhum incidente anterior registrado recentemente (Primeiro evento).\n"

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
                "temperature": 0.0
            }
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
            
            # Validação de Segurança (Whitelist)
            comando_sugerido = diagnostico_dict.get("comando_remediacao", "")
            if not self._validar_comando_seguro(comando_sugerido):
                logger.warning(f"ALERTA DE SEGURANÇA: Comando bloqueado: '{comando_sugerido}'")
                diagnostico_dict["comando_remediacao"] = "show logging (Comando original bloqueado por segurança)"
                diagnostico_dict["diagnostico"] += " [Aviso: Remediação restrita por política de segurança]."

            logger.info("Análise com RAG concluída e validada com sucesso.")
            return diagnostico_dict

        except requests.exceptions.ConnectionError:
            logger.warning("Ollama não está rodando localmente. Usando fallback.")
            return self._fallback_resposta(log_bruto)
        except Exception as e:
            logger.error(f"Erro inesperado ao consultar a IA: {e}")
            return self._fallback_resposta(log_bruto)

    def _validar_comando_seguro(self, comando: str) -> bool:
        """
        Nova regra: Permite qualquer comando de diagnóstico/leitura (como show com filtros),
        mas barra imediatamente qualquer tentativa de usar comandos destrutivos.
        """
        comando_limpo = comando.strip().lower()
        
        # Se contiver qualquer palavra perigosa, bloqueia na hora!
        for perigoso in self.COMANDOS_PROIBIDOS:
            if perigoso in comando_limpo:
                logger.warning(f"BLINDAGEM ATIVA: Comando destrutivo detectado e bloqueado: '{comando}'")
                return False
                
        return True

    def _fallback_resposta(self, log_bruto: str) -> Dict[str, Any]:
        return {
            "diagnostico": f"Análise offline de segurança com histórico. Log: {log_bruto[:60]}...",
            "severidade": "MEDIA",
            "comando_remediacao": "show logging"
        }