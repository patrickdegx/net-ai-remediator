import json
import logging
import socketserver
import threading
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger("EventTrigger")


def normalizar_evento(
    log_bruto: str,
    equipamento: Optional[str] = None,
    origem: str = "webhook",
) -> Dict[str, Any]:
    """Padroniza um evento recebido (Webhook ou Syslog) para alimentar o pipeline."""
    # Remove espaços extras e garante fallback seguro para o nome do equipamento.
    equipamento_limpo = (equipamento or "router-borda-sp01").strip() or "router-borda-sp01"
    log_limpo = log_bruto.strip()
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
        if "-" in token or "_" in token or token.startswith("router") or token.startswith("sw"):
            return token
    return "router-borda-sp01"


class WebhookEventServer:
    """Servidor HTTP leve (biblioteca padrão) para receber eventos via POST."""

    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 8080,
        callback_evento: Optional[Callable[[Dict[str, Any]], Any]] = None,
    ):
        self.host = host
        self.port = port
        self.callback_evento = callback_evento
        self._server: Optional[ThreadingHTTPServer] = None
        self._thread: Optional[threading.Thread] = None

    def _criar_handler(self):
        callback = self.callback_evento

        class EventoHandler(BaseHTTPRequestHandler):
            def do_POST(self):
                if self.path not in ("/webhook/evento", "/evento"):
                    self.send_response(404)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.end_headers()
                    self.wfile.write(json.dumps({"erro": "Rota não encontrada"}).encode("utf-8"))
                    return

                tamanho = int(self.headers.get("Content-Length", "0"))
                corpo_bruto = self.rfile.read(tamanho).decode("utf-8", errors="replace")

                try:
                    payload = json.loads(corpo_bruto) if corpo_bruto else {}
                except json.JSONDecodeError:
                    # Se enviarem texto puro no POST, trata como log bruto direto.
                    payload = {"log": corpo_bruto}

                log_msg = payload.get("log") or payload.get("log_bruto") or payload.get("mensagem") or ""
                if not str(log_msg).strip():
                    self.send_response(400)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.end_headers()
                    self.wfile.write(
                        json.dumps({"erro": "Campo 'log' (ou 'log_bruto') é obrigatório."}).encode("utf-8")
                    )
                    return

                evento = normalizar_evento(
                    log_bruto=str(log_msg),
                    equipamento=payload.get("equipamento") or payload.get("host"),
                    origem="webhook",
                )
                logger.info(f"Evento Webhook recebido | equipamento={evento['equipamento']}")

                resultado = None
                if callback:
                    resultado = callback(evento)

                self.send_response(202)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                resposta = {
                    "status": "aceito",
                    "equipamento": evento["equipamento"],
                    "incidente_id": getattr(resultado, "incidente_id", None),
                }
                self.wfile.write(json.dumps(resposta, ensure_ascii=False).encode("utf-8"))

            def log_message(self, format, *args):
                # Redireciona logs HTTP internos para o logger do módulo em nível DEBUG.
                logger.debug(f"HTTP Webhook: {format % args}")

        return EventoHandler

    def iniciar(self, bloqueante: bool = True) -> None:
        self._server = ThreadingHTTPServer((self.host, self.port), self._criar_handler())
        logger.info(f"Webhook escutando em http://{self.host}:{self.port}/webhook/evento")
        if bloqueante:
            try:
                self._server.serve_forever()
            except KeyboardInterrupt:
                logger.info("Webhook interrompido pelo usuário.")
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
            logger.info("Webhook encerrado.")


class _ReusableUDPServer(socketserver.UDPServer):
    allow_reuse_address = True


class SyslogUDPServer:
    """Listener UDP Syslog leve para capturar mensagens de rede em tempo real."""

    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 1514,
        callback_evento: Optional[Callable[[Dict[str, Any]], Any]] = None,
    ):
        self.host = host
        self.port = port
        self.callback_evento = callback_evento
        self._server: Optional[socketserver.UDPServer] = None
        self._thread: Optional[threading.Thread] = None

    def iniciar(self, bloqueante: bool = True) -> None:
        callback = self.callback_evento

        class SyslogHandler(socketserver.BaseRequestHandler):
            def handle(self):
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
                logger.info(f"Evento Syslog UDP recebido | equipamento={evento['equipamento']}")
                if callback:
                    callback(evento)

        self._server = _ReusableUDPServer((self.host, self.port), SyslogHandler)
        logger.info(f"Listener Syslog UDP escutando em {self.host}:{self.port}")

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