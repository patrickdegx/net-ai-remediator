import hmac
import json
import logging
import os
import socketserver
import threading
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable, Dict, Iterable, Optional, Set

# Logger dedicado do módulo de gatilhos para rastrear eventos, bloqueios e ciclo de vida dos servidores.
logger = logging.getLogger("EventTrigger")


def _normalizar_ips_permitidos(ips_permitidos: Optional[Iterable[str]]) -> Optional[Set[str]]:
    """Converte uma coleção de IPs em um set de strings limpas; retorna None se não houver filtro."""
    # Se o parâmetro for None ou vier vazio ([]), o filtro de IP fica DESATIVADO.
    # Assim, no laboratório local você não precisa ficar cadastrando IP toda hora.
    if not ips_permitidos:
        return None

    # Remove espaços em branco ao redor de cada IP e ignora entradas vazias.
    ips_limpos = {str(ip).strip() for ip in ips_permitidos if str(ip).strip()}

    # Se depois de limpar tudo não sobrar nenhum IP válido, retorna None para não travar o servidor.
    return ips_limpos or None


def _ip_esta_permitido(ip_origem: Optional[str], ips_permitidos: Optional[Set[str]]) -> bool:
    """Verifica se o IP de origem está na lista permitida (quando o filtro está ativo)."""
    # Quando ips_permitidos é None, não há restrição configurada: qualquer IP pode acessar.
    if ips_permitidos is None:
        return True

    # Se há filtro ativo mas não conseguimos identificar o IP do cliente, bloqueia por segurança.
    if not ip_origem:
        return False

    # Compara o IP limpo contra o set de IPs autorizados (busca O(1) em set).
    return ip_origem.strip() in ips_permitidos


def normalizar_evento(
    log_bruto: str,
    equipamento: Optional[str] = None,
    origem: str = "webhook",
) -> Dict[str, Any]:
    """Padroniza um evento recebido (Webhook ou Syslog) para alimentar o pipeline."""
    # Remove espaços extras e garante fallback seguro para o nome do equipamento.
    equipamento_limpo = (equipamento or "router-borda-sp01").strip() or "router-borda-sp01"
    log_limpo = log_bruto.strip()
    # Gera timestamp no fuso horário local atual no formato ISO 8601.
    agora_iso = datetime.now().astimezone().isoformat()

    return {
        "equipamento": equipamento_limpo,
        "log_bruto": log_limpo,
        "origem": origem,
        "recebido_em": agora_iso,
    }


def extrair_equipamento_syslog(mensagem: str) -> str:
    """Tenta extrair o host/equipamento de uma mensagem Syslog simples; usa fallback se não houver."""
    # Exemplo típico: "<134>Nov 23 14:00:00 router-borda-sp01 %BGP-5-ADJCHANGE: ..."
    partes = mensagem.strip().split()
    for token in partes[:5]:
        # Ignora prioridade <xxx>, meses e horários HH:MM:SS.
        if token.startswith("<") and token.endswith(">"):
            continue
        if ":" in token and len(token) == 8:
            continue
        if token in {"Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"}:
            continue
        if token.isdigit():
            continue
        # Heurística simples para identificar nomes de dispositivos de rede.
        if "-" in token or "_" in token or token.startswith("router") or token.startswith("sw"):
            return token
    return "router-borda-sp01"


class WebhookEventServer:
    """Servidor HTTP leve (biblioteca padrão) para receber eventos via POST."""

    def __init__(
        self,
        host: Optional[str] = None,
        port: int = 8080,
        callback_evento: Optional[Callable[[Dict[str, Any]], Any]] = None,
        token_autenticacao: Optional[str] = None,
        ips_permitidos: Optional[Iterable[str]] = None,
    ):
        # Ordem de prioridade do host:
        # 1) argumento `host` passado no construtor
        # 2) variável de ambiente `WEBHOOK_HOST`
        # 3) fallback `"0.0.0.0"` (escuta em todas as interfaces).
        host_resolvido = (host or os.getenv("WEBHOOK_HOST") or "0.0.0.0").strip() or "0.0.0.0"
        self.host = host_resolvido
        self.port = port
        self.callback_evento = callback_evento

        # Token opcional para autenticar chamadas HTTP via header `X-Webhook-Token`.
        # Se não for informado (ou ficar vazio), a autenticação por token fica desativada.
        token_limpo = (
            token_autenticacao if token_autenticacao is not None else os.getenv("WEBHOOK_TOKEN", "")
        ).strip()
        self.token_autenticacao: Optional[str] = token_limpo or None

        # Lista opcional de IPs permitidos para enviar eventos ao Webhook.
        self.ips_permitidos: Optional[Set[str]] = _normalizar_ips_permitidos(ips_permitidos)

        self._server: Optional[ThreadingHTTPServer] = None
        self._thread: Optional[threading.Thread] = None

    def _criar_handler(self):
        # Guardamos a referência da instância do servidor (`servidor_ref = self`) em vez de copiar
        # o valor atual de `ips_permitidos` ou `token_autenticacao` apenas uma vez na criação do handler.
        # Assim, se o atributo for alterado depois (ex.: `servidor.ips_permitidos = ...`), o handler
        # lê o valor vivo na hora de cada requisição.
        servidor_ref = self

        class EventoHandler(BaseHTTPRequestHandler):
            def _enviar_json(self, status_code: int, payload: Dict[str, Any]) -> None:
                # Helper centralizado para enviar respostas JSON com encoding UTF-8 e status HTTP correto.
                self.send_response(status_code)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps(payload, ensure_ascii=False).encode("utf-8"))

            def do_POST(self):
                # Normalizamos o atributo a cada requisição para suportar alterações dinâmicas
                # (inclusive se alguém atribuir uma lista ou set diretamente ao atributo após iniciar).
                ips_autorizados = _normalizar_ips_permitidos(servidor_ref.ips_permitidos)
                token_bruto = servidor_ref.token_autenticacao
                token_esperado = token_bruto.strip() if isinstance(token_bruto, str) and token_bruto.strip() else None

                # 1. Filtro opcional por IP de origem.
                # self.client_address no BaseHTTPRequestHandler é uma tupla (ip_cliente, porta_cliente).
                ip_cliente = self.client_address[0] if self.client_address else None
                if not _ip_esta_permitido(ip_cliente, ips_autorizados):
                    logger.warning(f"Webhook bloqueado: IP de origem não autorizado ({ip_cliente}).")
                    # HTTP 403 Forbidden: o cliente foi identificado, mas o IP não tem permissão.
                    self._enviar_json(403, {"erro": "Origem (IP) não autorizada."})
                    return

                # 2. Autenticação opcional por token no header `X-Webhook-Token`.
                if token_esperado:
                    token_recebido = (self.headers.get("X-Webhook-Token") or "").strip()
                    # hmac.compare_digest faz comparação em tempo constante para reduzir risco de
                    # timing attack (ataque que tenta adivinhar o token medindo o tempo de resposta).
                    if not token_recebido or not hmac.compare_digest(token_recebido, token_esperado):
                        logger.warning(f"Webhook bloqueado: token inválido ou ausente (IP={ip_cliente}).")
                        # HTTP 401 Unauthorized: credencial ausente ou inválida.
                        self._enviar_json(401, {"erro": "Não autorizado: token inválido ou ausente."})
                        return

                # 3. Validação da rota HTTP aceita.
                if self.path not in ("/webhook/evento", "/evento"):
                    self._enviar_json(404, {"erro": "Rota não encontrada"})
                    return

                # Lê o corpo da requisição com base no Content-Length.
                tamanho = int(self.headers.get("Content-Length", "0"))
                corpo_bruto = self.rfile.read(tamanho).decode("utf-8", errors="replace")

                try:
                    payload = json.loads(corpo_bruto) if corpo_bruto else {}
                except json.JSONDecodeError:
                    # Se enviarem texto puro no POST, trata como log bruto direto.
                    payload = {"log": corpo_bruto}

                # Aceita diferentes nomes de campo para facilitar integração com sistemas externos.
                log_msg = payload.get("log") or payload.get("log_bruto") or payload.get("mensagem") or ""
                if not str(log_msg).strip():
                    self._enviar_json(400, {"erro": "Campo 'log' (ou 'log_bruto') é obrigatório."})
                    return

                evento = normalizar_evento(
                    log_bruto=str(log_msg),
                    equipamento=payload.get("equipamento") or payload.get("host"),
                    origem="webhook",
                )
                logger.info(f"Evento Webhook recebido | origem_ip={ip_cliente} | equipamento={evento['equipamento']}")

                # Dispara o callback do pipeline (se houver) e tenta extrair incidente_id caso exista.
                resultado = None
                if servidor_ref.callback_evento:
                    resultado = servidor_ref.callback_evento(evento)

                resposta = {
                    "status": "aceito",
                    "equipamento": evento["equipamento"],
                    "incidente_id": getattr(resultado, "incidente_id", None),
                }
                # HTTP 202 Accepted: evento recebido e encaminhado para processamento.
                self._enviar_json(202, resposta)

            def log_message(self, format, *args):
                # Redireciona logs HTTP internos para o logger do módulo em nível DEBUG para não poluir o console.
                logger.debug(f"HTTP Webhook: {format % args}")

        return EventoHandler

    def iniciar(self, bloqueante: bool = True) -> None:
        # Cria o servidor HTTP multi-thread no host e porta configurados.
        self._server = ThreadingHTTPServer((self.host, self.port), self._criar_handler())
        logger.info(
            f"Webhook escutando em http://{self.host}:{self.port}/webhook/evento "
            f"(auth_token={'ativo' if self.token_autenticacao else 'desativado'}, "
            f"filtro_ip={'ativo' if self.ips_permitidos else 'desativado'})"
        )
        if bloqueante:
            try:
                self._server.serve_forever()
            except KeyboardInterrupt:
                logger.info("Webhook interrompido pelo usuário.")
            finally:
                self.parar()
        else:
            # Modo não bloqueante roda em thread daemon (útil para testes e execução integrada).
            self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
            self._thread.start()

    def parar(self) -> None:
        if self._server:
            self._server.shutdown()
            self._server.server_close()
            self._server = None
            logger.info("Webhook encerrado.")


class _ReusableUDPServer(socketserver.UDPServer):
    # Subclasse isolada para ativar SO_REUSEADDR apenas neste servidor UDP,
    # evitando mutar o atributo de classe global socketserver.UDPServer.allow_reuse_address.
    allow_reuse_address = True


class SyslogUDPServer:
    """Listener UDP Syslog leve para capturar mensagens de rede em tempo real."""

    def __init__(
        self,
        host: Optional[str] = None,
        port: int = 1514,
        callback_evento: Optional[Callable[[Dict[str, Any]], Any]] = None,
        ips_permitidos: Optional[Iterable[str]] = None,
    ):
        # Prioridade do host: argumento `host` -> env `SYSLOG_HOST` -> `"0.0.0.0"`.
        host_resolvido = (host or os.getenv("SYSLOG_HOST") or "0.0.0.0").strip() or "0.0.0.0"
        self.host = host_resolvido
        self.port = port
        self.callback_evento = callback_evento

        # UDP não possui cabeçalhos HTTP como X-Webhook-Token, então o controle de origem aqui é por IP.
        self.ips_permitidos: Optional[Set[str]] = _normalizar_ips_permitidos(ips_permitidos)

        self._server: Optional[socketserver.UDPServer] = None
        self._thread: Optional[threading.Thread] = None

    def iniciar(self, bloqueante: bool = True) -> None:
        # Mesma ideia do Webhook: ler `servidor_ref.ips_permitidos` e `servidor_ref.callback_evento`
        # em tempo real dentro do handler para refletir mudanças feitas após `iniciar()`.
        servidor_ref = self

        class SyslogHandler(socketserver.BaseRequestHandler):
            def handle(self):
                ips_autorizados = _normalizar_ips_permitidos(servidor_ref.ips_permitidos)

                # Em UDP, self.client_address traz (ip_remetente, porta_remetente).
                # Se houver filtro de IP ativo e o remetente não estiver autorizado, descarta o pacote.
                ip_remetente = self.client_address[0] if self.client_address else None
                if not _ip_esta_permitido(ip_remetente, ips_autorizados):
                    logger.warning(f"Syslog UDP descartado: IP de origem não autorizado ({ip_remetente}).")
                    return

                # self.request em UDPServer é uma tupla (bytes_do_datagrama, socket_do_servidor).
                dados_bytes = self.request[0]
                mensagem = dados_bytes.decode("utf-8", errors="replace").strip()
                if not mensagem:
                    return

                equipamento = extrair_equipamento_syslog(mensagem)
                evento = normalizar_evento(
                    log_bruto=mensagem,
                    equipamento=equipamento,
                    origem="syslog_udp",
                )
                logger.info(
                    f"Evento Syslog UDP recebido | origem_ip={ip_remetente} | equipamento={evento['equipamento']}"
                )
                if servidor_ref.callback_evento:
                    servidor_ref.callback_evento(evento)

        self._server = _ReusableUDPServer((self.host, self.port), SyslogHandler)
        logger.info(
            f"Listener Syslog UDP escutando em {self.host}:{self.port} "
            f"(filtro_ip={'ativo' if self.ips_permitidos else 'desativado'})"
        )

        if bloqueante:
            try:
                self._server.serve_forever()
            except KeyboardInterrupt:
                logger.info("Listener Syslog UDP interrompido pelo usuário.")
            finally:
                self.parar()
        else:
            self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
            self._thread.start()

    def parar(self) -> None:
        if self._server:
            self._server.shutdown()
            self._server.server_close()
            self._server = None
            logger.info("Listener Syslog UDP encerrado.")