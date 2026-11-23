import json
import os
import socket
import sys
import time
from urllib import request

# Garante que a raiz do projeto esteja no sys.path para importar src/triggers/event_trigger.py.
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.triggers.event_trigger import (
    SyslogUDPServer,
    WebhookEventServer,
    extrair_equipamento_syslog,
    normalizar_evento,
)


def testar_normalizacao_e_syslog_parser():
    # Exibe o cabeçalho do teste de normalização de eventos.
    print("--- TESTE EVENT_TRIGGER: NORMALIZAÇÃO E PARSER SYSLOG ---")

    eq_extraido = extrair_equipamento_syslog(
        "<134>Nov 23 14:10:00 router-borda-sp01 %BGP-5-ADJCHANGE: neighbor 10.255.0.2 Down"
    )
    assert eq_extraido == "router-borda-sp01"

    evento = normalizar_evento(
        log_bruto="  %LINK-3-UPDOWN: Interface GigabitEthernet0/1, changed state to down  ",
        equipamento=" sw-acesso-01 ",
        origem="webhook",
    )
    assert evento["equipamento"] == "sw-acesso-01"
    assert evento["log_bruto"] == "%LINK-3-UPDOWN: Interface GigabitEthernet0/1, changed state to down"
    assert evento["origem"] == "webhook"
    assert evento["recebido_em"]

    print("OK -> Normalização e extração de equipamento Syslog validadas.")


def testar_webhook_e_syslog_servers():
    # Exibe o cabeçalho do teste dos servidores Webhook HTTP e Syslog UDP.
    print("--- TESTE EVENT_TRIGGER: WEBHOOK HTTP E SYSLOG UDP ---")

    eventos_recebidos = []
    webhook_port = 18080
    syslog_port = 11514

    webhook = WebhookEventServer(
        host="127.0.0.1",
        port=webhook_port,
        callback_evento=lambda ev: eventos_recebidos.append(ev),
    )
    syslog = SyslogUDPServer(
        host="127.0.0.1",
        port=syslog_port,
        callback_evento=lambda ev: eventos_recebidos.append(ev),
    )

    webhook.iniciar(bloqueante=False)
    syslog.iniciar(bloqueante=False)
    time.sleep(0.2)

    try:
        # 1. Envia evento HTTP POST para o Webhook.
        corpo = json.dumps(
            {
                "equipamento": "router-borda-sp01",
                "log": "%BGP-5-ADJCHANGE: neighbor 10.255.0.2 Down",
            }
        ).encode("utf-8")
        req = request.Request(
            f"http://127.0.0.1:{webhook_port}/webhook/evento",
            data=corpo,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with request.urlopen(req, timeout=3) as resp:
            assert resp.status == 202

        # 2. Envia pacote UDP Syslog para o listener.
        msg_syslog = b"<134>Nov 23 14:15:00 router-dist-sp02 %OSPF-5-ADJCHG: Process 1, Nbr 10.0.0.2 on Gi0/0 from FULL to DOWN"
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.sendto(msg_syslog, ("127.0.0.1", syslog_port))

        time.sleep(0.2)

        assert len(eventos_recebidos) == 2
        assert eventos_recebidos[0]["origem"] == "webhook"
        assert eventos_recebidos[0]["equipamento"] == "router-borda-sp01"
        assert eventos_recebidos[1]["origem"] == "syslog_udp"
        assert eventos_recebidos[1]["equipamento"] == "router-dist-sp02"

        print("OK -> Webhook HTTP e Syslog UDP receberam e normalizaram os eventos.")
    finally:
        webhook.parar()
        syslog.parar()


if __name__ == "__main__":
    testar_normalizacao_e_syslog_parser()
    testar_webhook_e_syslog_servers()
    print("--- TODOS OS TESTES DO EVENT_TRIGGER CONCLUÍDOS ---")