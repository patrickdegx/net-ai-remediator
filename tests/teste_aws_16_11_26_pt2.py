import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.cloud.aws_client import AWSManager


def testar_dynamodb():
    aws = AWSManager()
    tabela = "net-ai-incidentes"

    print("\n--- 1. CRIANDO TABELA NO DYNAMODB ---")
    aws.criar_tabela_incidentes(tabela)

    print("\n--- 2. REGISTRANDO INCIDENTE ---")
    aws.registrar_incidente(
        table_name=tabela,
        incidente_id="INC-2026-001",
        equipamento="router-borda-sp01",
        severidade="CRITICA",
        diagnostico_ia="Queda de sessão BGP por erro de MTU na interface eth0",
        s3_key="relatorios/2026-11/incidente_001.json",
        status="ANALISADO"
    )

    print("\n--- 3. BUSCANDO INCIDENTE ---")
    dados = aws.buscar_incidente(tabela, "INC-2026-001")
    print("Dados recuperados:", dados)

    print("\n--- 4. ATUALIZANDO STATUS APÓS REMEDIAÇÃO ---")
    aws.atualizar_status_incidente(tabela, "INC-2026-001", "REMEDIADO")
    dados_atualizados = aws.buscar_incidente(tabela, "INC-2026-001")
    print("Status atualizado:", dados_atualizados["status"] if dados_atualizados else "Erro")


if __name__ == "__main__":
    testar_dynamodb()