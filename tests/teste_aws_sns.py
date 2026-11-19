import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.cloud.aws_client import AWSManager


def testar_sns():
    aws = AWSManager()

    print("\n--- 1. CRIANDO TÓPICO DE ALERTAS CRÍTICOS ---")
    topic_arn = aws.criar_topico_alertas("net-ai-alertas-criticos")
    if not topic_arn:
        return

    print("\n--- 2. INSCREVENDO E-MAIL DA EQUIPE DE REDES (NOC) ---")
    aws.inscrever_alerta(
        topic_arn=topic_arn,
        protocolo="email",
        endpoint="noc-engenharia@empresa.com.br"
    )

    print("\n--- 3. DISPARANDO ALERTA DE INCIDENTE CRÍTICO ---")
    corpo_alerta = (
        "INCIDENTE DETECTADO PELO NET-AI REMEDIATOR\n"
        "Equipamento: router-borda-sp01 (10.0.0.1)\n"
        "Severidade: CRITICA\n"
        "Diagnóstico IA: Queda de sessão BGP por erro de MTU na interface eth0.\n"
        "Relatório completo (S3 Presigned URL): http://localhost:4566/net-ai-bucket/relatorios/incidente_001.json"
    )

    msg_id = aws.disparar_alerta_critico(
        topic_arn=topic_arn,
        assunto="[CRÍTICO] Falha BGP detectada em router-borda-sp01",
        mensagem=corpo_alerta
    )
    print(f"Notificação enviada com sucesso! ID da Mensagem: {msg_id}")


if __name__ == "__main__":
    testar_sns()