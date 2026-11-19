import sys
import os
import json

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.cloud.aws_client import AWSManager


def testar_evolucoes_s3():
    aws = AWSManager()
    bucket = "net-ai-bucket-teste-2026"
    aws.criar_bucket(bucket)

    print("\n--- 1. TESTE DE ESCRITA DIRETO DA MEMÓRIA + METADADOS ---")
    relatorio_ia = json.dumps({
        "equipamento": "router-borda-sp01",
        "anomalia": "BGP Flap detectado na interface eth0",
        "acao_sugerida": "Aplicar route-map de damping e verificar MTU"
    }, indent=2, ensure_ascii=False)

    chave_relatorio = "relatorios/2026-11/incidente_001.json"
    chave_log = "logs/router-borda-sp01/syslog_raw.txt"

    aws.enviar_conteudo_texto(
        conteudo=relatorio_ia,
        bucket_name=bucket,
        object_name=chave_relatorio,
        metadata={"equipamento": "router-borda-sp01", "severidade": "critica"},
        content_type="application/json"
    )
    aws.enviar_conteudo_texto(
        conteudo="Nov 16 17:10:01 router-borda-sp01 bgpd[1024]: Neighbor 10.0.0.2 Down",
        bucket_name=bucket,
        object_name=chave_log
    )

    print("\n--- 2. TESTE DE VERIFICAÇÃO DE EXISTÊNCIA (HEAD) ---")
    print(f"Relatório existe? {aws.arquivo_existe(bucket, chave_relatorio)}")
    print(f"Arquivo fantasma existe? {aws.arquivo_existe(bucket, 'relatorios/nao_existe.json')}")

    print("\n--- 3. TESTE DE LISTAGEM FILTRADA POR PREFIXO ---")
    print("Apenas relatórios:", aws.listar_arquivos(bucket, prefixo="relatorios/"))
    print("Apenas logs:", aws.listar_arquivos(bucket, prefixo="logs/"))

    print("\n--- 4. TESTE DE METADADOS E TAGS DINÂMICAS ---")
    print("Metadados gravados:", aws.obter_metadados(bucket, chave_relatorio))

    aws.definir_tags(bucket, chave_relatorio, {"status": "pendente_revisao", "turno": "noite"})
    print("Tags lidas:", aws.obter_tags(bucket, chave_relatorio))

    print("\n--- 5. TESTE DE LEITURA DIRETO PARA A MEMÓRIA ---")
    conteudo_lido = aws.ler_conteudo_texto(bucket, chave_relatorio)
    print(f"Conteúdo recuperado do S3:\n{conteudo_lido}")

    # Limpeza final dos objetos de teste
    aws.deletar_arquivo(bucket, chave_relatorio)
    aws.deletar_arquivo(bucket, chave_log)


if __name__ == "__main__":
    testar_evolucoes_s3()