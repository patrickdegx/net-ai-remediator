import json
import os
import socket
import sys
import time
import urllib.error
import urllib.request

# Garante que a raiz do projeto esteja no sys.path ao rodar o arquivo diretamente
RAIZ_PROJETO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if RAIZ_PROJETO not in sys.path:
    sys.path.insert(0, RAIZ_PROJETO)

from src.triggers.event_trigger import (
    SyslogUDPServer,
    WebhookEventServer,
    extrair_equipamento_syslog,
    normalizar_evento,
)


def _porta_livre(tipo_socket: int = socket.SOCK_STREAM) -> int:
    with socket.socket(socket.AF_INET, tipo_socket) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def testar_normalizar_e_syslog_host():
    ev_padrao = normalizar_evento("  %BGP-5-ADJCHANGE: neighbor 10.255.0.2 Down  ")
    assert ev_padrao["equipamento"] == "router-borda-sp01"
    assert ev_padrao["log_bruto"] == "%BGP-5-ADJCHANGE: neighbor 10.255.0.2 Down"
    assert ev_padrao["origem"] == "webhook"
    assert "T" in ev_padrao["recebido_em"]

    ev_eq = normalizar_evento(" %LINK-3-UPDOWN: Gi0/1 down ", equipamento="  sw-core-sp02 ", origem="syslog_udp")
    assert ev_eq["equipamento"] == "sw-core-sp02"
    assert ev_eq["origem"] == "syslog_udp"

    msg_syslog = "<134>Nov 24 11:30:00 rtr-borda-sp01 %BGP-5-ADJCHANGE: neighbor 10.255.255.2 Down"
    assert extrair_equipamento_syslog(msg_syslog) == "rtr-borda-sp01"
    assert extrair_equipamento_syslog("mensagem sem hostname identificavel") == "router-borda-sp01"

    print("OK: normalizar_evento e extrair_equipamento_syslog validados.")


def testar_webhook_server():
    eventos_recebidos = []

    def callback(ev):
        eventos_recebidos.append(ev)
        return {"incidente_id": "INC-TESTE-001"}

    porta = _porta_livre(socket.SOCK_STREAM)
    servidor = WebhookEventServer(host="127.0.0.1", port=porta, callback_evento=callback)
    servidor.iniciar(bloqueante=False)
    time.sleep(0.2)

    try:
        url = f"http://127.0.0.1:{porta}/webhook/evento"
        corpo = json.dumps({"equipamento": "rtr-oob-01", "log": "%OSPF-5-ADJCHG: Process 1"}).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=corpo,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=3) as resp:
            assert resp.status == 202
            dados = json.loads(resp.read().decode("utf-8"))
            assert dados["status"] == "aceito"
            assert dados["equipamento"] == "rtr-oob-01"

        assert len(eventos_recebidos) == 1
        assert eventos_recebidos[0]["origem"] == "webhook"

        # Payload sem campo de log deve retornar 400
        req_invalido = urllib.request.Request(
            url,
            data=json.dumps({"equipamento": "rtr-oob-01"}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            urllib.request.urlopen(req_invalido, timeout=3)
            assert False, "Esperava erro HTTP 400"
        except urllib.error.HTTPError as err:
            assert err.code == 400

        # Rota inexistente deve retornar 404
        req_404 = urllib.request.Request(
            f"http://127.0.0.1:{porta}/rota-inexistente",
            data=b"{}",
            method="POST",
        )
        try:
            urllib.request.urlopen(req_404, timeout=3)
            assert False, "Esperava erro HTTP 404"
        except urllib.error.HTTPError as err:
            assert err.code == 404
    finally:
        servidor.parar()

    print("OK: WebhookEventServer validado (202, 400, 404 e callback).")


def testar_syslog_udp_server():
    eventos_recebidos = []
    porta = _porta_livre(socket.SOCK_DGRAM)

    servidor = SyslogUDPServer(
        host="127.0.0.1",
        port=porta,
        callback_evento=lambda ev: eventos_recebidos.append(ev),
    )
    servidor.iniciar(bloqueante=False)
    time.sleep(0.2)

    try:
        mensagem = b"<134>Nov 24 11:35:00 edge-gw-01 %SEC-6-IPACCESSLOGP: list 101 denied tcp 10.0.0.5 -> 10.0.0.1"
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock_cli:
            sock_cli.sendto(mensagem, ("127.0.0.1", porta))

        # Aguarda brevemente a thread do handler processar o datagrama
        for _ in range(20):
            if eventos_recebidos:
                break
            time.sleep(0.05)

        assert len(eventos_recebidos) == 1
        assert eventos_recebidos[0]["equipamento"] == "edge-gw-01"
        assert eventos_recebidos[0]["origem"] == "syslog_udp"
    finally:
        servidor.parar()

    print("OK: SyslogUDPServer validado via datagrama UDP.")


if __name__ == "__main__":
    testar_normalizar_e_syslog_host()
    testar_webhook_server()
    testar_syslog_udp_server()
    print("\nTodos os testes de event_trigger passaram!")