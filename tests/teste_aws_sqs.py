import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.cloud.aws_client import AWSManager


def testar_sqs():
    aws = AWSManager()

    print("\n--- 1. CRIANDO A FILA DE ALERTAS ---")
    url_fila = aws.criar_fila("net-ai-alertas-queue")
    if not url_fila:
        return

    print("\n--- 2. SIMULANDO 2 ROTEADORES ENVIANDO FALHAS PARA A FILA ---")
    alerta_1 = {
        "equipamento": "router-borda-sp01",
        "ip": "10.0.0.1",
        "erro": "BGP Neighbor 10.0.0.2 Down",
        "severidade": "CRITICA"
    }
    alerta_2 = {
        "equipamento": "switch-core-rj01",
        "ip": "10.0.1.5",
        "erro": "Alta utilizacao de CPU (94%)",
        "severidade": "ALTA"
    }

    aws.enviar_alerta_fila(url_fila, alerta_1)
    aws.enviar_alerta_fila(url_fila, alerta_2)

    print("\n--- 3. CONSUMINDO ALERTAS DA FILA (COMO A IA FARIA) ---")
    alertas_recebidos = aws.consumir_alertas_fila(url_fila, max_mensagens=5)
    for idx, alerta in enumerate(alertas_recebidos, start=1):
        print(f"Ticket #{idx}: [{alerta['severidade']}] {alerta['equipamento']} -> {alerta['erro']}")

    print("\n--- 4. VERIFICANDO SE A FILA FICOU VAZIA APÓS CONSUMO ---")
    restantes = aws.consumir_alertas_fila(url_fila)
    print(f"Mensagens restantes na fila: {len(restantes)}")


if __name__ == "__main__":
    testar_sqs()