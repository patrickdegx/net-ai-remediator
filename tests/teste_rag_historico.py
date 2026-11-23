import os
import sys
import uuid

# Garante que a raiz do projeto esteja no sys.path para importar 'src' e 'main'
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.cloud.aws_client import AWSManager
from src.core.config import AppConfig


def testar_historico_rag() -> None:
    print("=== INICIANDO TESTE DO HISTÓRICO DYNAMODB (RAG) ===")
    config = AppConfig()

    aws = AWSManager(
        endpoint_url=config.localstack_endpoint,
        region_name=config.aws_region,
    )

    equipamento_teste = "router-borda-sp01"
    sufixo = uuid.uuid4().hex[:6].upper()
    inc_1 = f"INC-TESTE-01-{sufixo}"
    inc_2 = f"INC-TESTE-02-{sufixo}"

    assert aws.criar_tabela_incidentes(config.dynamodb_table), "Falha ao criar/garantir tabela."

    assert aws.registrar_incidente(
        table_name=config.dynamodb_table,
        incidente_id=inc_1,
        equipamento=equipamento_teste,
        severidade="MEDIA",
        diagnostico_ia="Primeiro evento de flap na interface Ethernet0/0.",
        s3_key=f"relatorios/{inc_1}.json",
        status="REMEDIADO",
    ), "Falha ao registrar incidente 1."

    assert aws.registrar_incidente(
        table_name=config.dynamodb_table,
        incidente_id=inc_2,
        equipamento=equipamento_teste,
        severidade="ALTA",
        diagnostico_ia="Segundo evento BGP hold timer expired no mesmo vizinho.",
        s3_key=f"relatorios/{inc_2}.json",
        status="ANALISADO",
    ), "Falha ao registrar incidente 2."

    historico = aws.buscar_historico_equipamento(
        table_name=config.dynamodb_table,
        equipamento=equipamento_teste,
        limite=5,
    )

    ids_retornados = [item.get("incidente_id") for item in historico]
    print(f"Total retornado: {len(historico)}")
    print(f"IDs retornados: {ids_retornados}")

    assert inc_1 in ids_retornados, f"{inc_1} não encontrado no histórico."
    assert inc_2 in ids_retornados, f"{inc_2} não encontrado no histórico."

    print("=== TESTE DO HISTÓRICO DYNAMODB CONCLUÍDO COM SUCESSO! ===")


if __name__ == "__main__":
    testar_historico_rag()