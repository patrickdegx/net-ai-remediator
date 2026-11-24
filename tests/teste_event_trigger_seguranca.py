import json
import os
import socket
import sys
import time
import urllib.error
import urllib.request

# Garante que a raiz do projeto esteja no sys.path ao executar o script diretamente
RAIZ_PROJETO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if RAIZ_PROJETO not in sys.path:
    sys.path.insert(0, RAIZ_PROJETO)

from src.triggers.event_trigger import SyslogUDPServer, WebhookEventServer


def _porta_livre(tipo_socket: int = socket.SOCK_STREAM) -> int:
    # Solicita ao sistema operacional uma porta livre aleatória para evitar conflitos em testes
    with socket.socket(socket.AF_INET, tipo_socket) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def testar_webhook_com_token_e_ip():
    eventos_recebidos = []
    porta = _porta_livre(socket.SOCK_STREAM)
    token_secreto = "segredo-lab-123"

    # Configura o Webhook exigindo token e permitindo apenas 127.0.0.1
    servidor = WebhookEventServer(
        host="127.0.0.1",
        port=porta,
        callback_evento=lambda ev: eventos_recebidos.append(ev),
        token_autenticacao=token_secreto,
        ips_permitidos=["127.0.0.1"],
    )
    servidor.iniciar(bloqueante=False)
    time.sleep(0.2)

    try:
        url = f"http://127.0.0.1:{porta}/webhook/evento"
        payload = json.dumps({"equipamento": "rtr-borda-sp01", "log": "%BGP-5-ADJCHANGE: Down"}).encode("utf-8")

        # 1. Sem header X-Webhook-Token -> deve retornar 401
        req_sem_token = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            urllib.request.urlopen(req_sem_token, timeout=3)
            assert False, "Esperava HTTP 401 quando o token está ausente"
        except urllib.error.HTTPError as err:
            assert err.code == 401

        # 2. Com token incorreto -> deve retornar 401
        req_token_errado = urllib.request.Request(
            url,
            data=payload,
            headers={
                "Content-Type": "application/json",
                "X-Webhook-Token": "token-invalido",
            },
            method="POST",
        )
        try:
            urllib.request.urlopen(req_token_errado, timeout=3)
            assert False, "Esperava HTTP 401 quando o token é inválido"
        except urllib.error.HTTPError as err:
            assert err.code == 401

        # 3. Com token válido e IP permitido (127.0.0.1) -> deve retornar 202 e disparar callback
        req_valido = urllib.request.Request(
            url,
            data=payload,
            headers={
                "Content-Type": "application/json",
                "X-Webhook-Token": token_secreto,
            },
            method="POST",
        )
        with urllib.request.urlopen(req_valido, timeout=3) as resp:
            assert resp.status == 202

        assert len(eventos_recebidos) == 1
        assert eventos_recebidos[0]["equipamento"] == "rtr-borda-sp01"

        # 4. Alteração dinâmica em tempo de execução: restringe IP para 192.0.2.99 -> 127.0.0.1 deve receber 403
        servidor.ips_permitidos = {"192.0.2.99"}
        try:
            urllib.request.urlopen(req_valido, timeout=3)
            assert False, "Esperava HTTP 403 após alterar ips_permitidos dinamicamente"
        except urllib.error.HTTPError as err:
            assert err.code == 403

        # Nenhum evento extra deve ter passado após o bloqueio 403
        assert len(eventos_recebidos) == 1
    finally:
        servidor.parar()

    # 5. Instância já iniciada com ips_permitidos=["192.0.2.99"] deve bloquear 127.0.0.1 logo de cara (403)
    porta_bloqueada = _porta_livre(socket.SOCK_STREAM)
    servidor_bloqueado = WebhookEventServer(
        host="127.0.0.1",
        port=porta_bloqueada,
        callback_evento=lambda ev: eventos_recebidos.append(ev),
        token_autenticacao=None,
        ips_permitidos=["192.0.2.99"],
    )
    servidor_bloqueado.iniciar(bloqueante=False)
    time.sleep(0.2)

    try:
        url_bloqueada = f"http://127.0.0.1:{porta_bloqueada}/webhook/evento"
        payload = json.dumps({"equipamento": "rtr-borda-sp01", "log": "%LINK-3-UPDOWN: Gi0/0 down"}).encode("utf-8")
        req_livre_de_token = urllib.request.Request(
            url_bloqueada,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            urllib.request.urlopen(req_livre_de_token, timeout=3)
            assert False, "Esperava HTTP 403 em instância configurada com ips_permitidos=['192.0.2.99']"
        except urllib.error.HTTPError as err:
            assert err.code == 403

        assert len(eventos_recebidos) == 1
    finally:
        servidor_bloqueado.parar()

    print("OK: WebhookEventServer com token (401/202), bloqueio inicial (403) e troca dinâmica validado.")


def testar_syslog_udp_filtro_ip():
    eventos_recebidos = []
    porta = _porta_livre(socket.SOCK_DGRAM)

    # Restringe o Syslog UDP apenas a um IP que não enviará pacote neste teste
    servidor = SyslogUDPServer(
        host="127.0.0.1",
        port=porta,
        callback_evento=lambda ev: eventos_recebidos.append(ev),
        ips_permitidos=["192.0.2.50"],
    )
    servidor.iniciar(bloqueante=False)
    time.sleep(0.2)

    try:
        mensagem = b"<134>Nov 24 12:00:00 sw-core-01 %LINK-3-UPDOWN: Gi0/1 down"
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock_cli:
            sock_cli.sendto(mensagem, ("127.0.0.1", porta))

        time.sleep(0.2)
        # Como 127.0.0.1 não está em ["192.0.2.50"], o pacote deve ser descartado
        assert len(eventos_recebidos) == 0

        # Agora libera 127.0.0.1 dinamicamente e envia novamente -> deve processar
        servidor.ips_permitidos = {"127.0.0.1"}
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock_cli:
            sock_cli.sendto(mensagem, ("127.0.0.1", porta))

        for _ in range(20):
            if eventos_recebidos:
                break
            time.sleep(0.05)

        assert len(eventos_recebidos) == 1
        assert eventos_recebidos[0]["equipamento"] == "sw-core-01"
        assert eventos_recebidos[0]["origem"] == "syslog_udp"
    finally:
        servidor.parar()

    print("OK: SyslogUDPServer com filtro de IP permitido e atualização dinâmica validado.")


if __name__ == "__main__":
    testar_webhook_com_token_e_ip()
    testar_syslog_udp_filtro_ip()
    print("\nTodos os testes de segurança de event_trigger passaram!")