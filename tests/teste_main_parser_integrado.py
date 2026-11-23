import json
import os
import sys

# Garante que a raiz do projeto esteja no sys.path para importar main e src/.
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import main
from src.cloud.aws_client import AWSManager
from src.core.config import AppConfig


def testar_main_com_ollama_e_localstack():
    # Exibe o cabeçalho de início do teste integrado do main.py.
    print("--- TESTE DO MAIN.PY: CONTEXTO TEXTFSM + OLLAMA + LOCALSTACK (S3) ---")

    # Configura o logging padrão para acompanhar todas as etapas do pipeline no terminal.
    main.configurar_logging()

    # Executa o pipeline completo usando o driver simulado, Ollama e LocalStack.
    incidente = main.executar_pipeline(tipo_driver="simulador")

    # Confere que o incidente concluiu com status REMEDIADO e gerou chave no S3.
    assert incidente is not None
    assert incidente.status == "REMEDIADO"
    assert incidente.s3_key, "Esperava que o relatório JSON tivesse sido salvo no S3 com s3_key preenchido."

    # Carrega a configuração do projeto e lê o JSON salvo no S3 via LocalStack.
    config = AppConfig()
    aws = AWSManager(
        endpoint_url=config.localstack_endpoint,
        region_name=config.aws_region,
    )
    conteudo_s3 = aws.ler_conteudo_texto(config.s3_bucket, incidente.s3_key)
    assert conteudo_s3, "Não foi possível ler o relatório JSON salvo no S3."

    # Converte o JSON do S3 para dicionário e valida que cli_estruturada foi incluída.
    relatorio = json.loads(conteudo_s3)
    assert "cli_estruturada" in relatorio, "A chave 'cli_estruturada' deveria estar no relatório do S3."
    assert isinstance(relatorio["cli_estruturada"], list) and len(relatorio["cli_estruturada"]) > 0

    print(f"\n[S3 BUCKET / KEY]: {config.s3_bucket} / {incidente.s3_key}")
    print("[RELATÓRIO JSON SALVO NO S3]:")
    print(json.dumps(relatorio, ensure_ascii=False, indent=2))
    print("\n--- TESTE DO MAIN.PY CONCLUÍDO COM SUCESSO ---")


if __name__ == "__main__":
    testar_main_com_ollama_e_localstack()