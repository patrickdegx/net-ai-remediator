# Módulos padrão do Python: json para serializar relatórios com segurança, logging para
# mensagens estruturadas, uuid para gerar IDs únicos e datetime para carimbar data/hora.
import json
import logging
import uuid
from datetime import datetime

# Importações internas do projeto (cada pacote tem seu __init__.py).
from src.ai.analyzer import NetworkAIAnalyzer
from src.cloud.aws_client import AWSManager
from src.core.config import AppConfig
from src.core.models import DiagnosticoIA, IncidenteRede
from src.network.drivers import NetworkDriverFactory


def configurar_logging() -> None:
    # Configura o log global apenas uma vez no ponto de entrada da aplicação.
    # Como os outros módulos usam logging.getLogger("Nome"), todos herdam esse formato.
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def executar_pipeline(tipo_driver: str = "simulador") -> IncidenteRede:
    logger = logging.getLogger("MainPipeline")

    # 1. Carrega configurações centralizadas (hosts, nomes de bucket/tabela/fila/tópico, Ollama).
    config = AppConfig()
    logger.info(f"Iniciando pipeline | Endpoint LocalStack: {config.localstack_endpoint}")

    # 2. Instancia o driver de rede via Factory Pattern (ex.: "simulador" ou "netmiko").
    driver = NetworkDriverFactory.criar_driver(
        tipo_driver,
        nome_equipamento="router-borda-sp01",
    )

    # 3. Coleta os logs recentes do equipamento.
    log_bruto = driver.coletar_logs_recentes()
    equipamento = getattr(driver, "nome_equipamento", "router-borda-sp01")

    # 4. Cria um ID único no fuso horário local e instancia a dataclass IncidenteRede.
    agora_local = datetime.now().astimezone()
    incidente_id = f"INC-{agora_local.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6].upper()}"
    incidente = IncidenteRede(
        incidente_id=incidente_id,
        equipamento=equipamento,
        severidade="PENDENTE",
        diagnostico="",
        comando_remediacao="",
        status="COLETADO",
    )

    # 5. Envia o log para o analisador de IA (Ollama + RAG + validação de comando seguro).
    analyzer = NetworkAIAnalyzer(
        modelo=config.ollama_model,
        ollama_url=config.ollama_url,
    )
    resultado_ia = analyzer.analisar_log_rede(
        log_bruto=log_bruto,
        equipamento=incidente.equipamento,
        historico_recente=None,  # Próxima evolução: buscar histórico real do DynamoDB.
    )

    # 6. Preenche a dataclass DiagnosticoIA e atualiza o IncidenteRede.
    diagnostico_obj = DiagnosticoIA(
        diagnostico=resultado_ia.get("diagnostico", "Sem diagnóstico detalhado."),
        severidade=resultado_ia.get("severidade", "MEDIA"),
        comando_remediacao=resultado_ia.get("comando_remediacao", "show logging"),
    )

    incidente.diagnostico = diagnostico_obj.diagnostico
    incidente.severidade = diagnostico_obj.severidade
    incidente.comando_remediacao = diagnostico_obj.comando_remediacao
    incidente.status = "ANALISADO"

    # Guarda a referência do AWSManager fora do bloco try para podermos sincronizar o status
    # no DynamoDB depois que a remediação for aplicada.
    aws = None

    # 7. Integração com LocalStack / AWS (S3, DynamoDB, SQS, SNS).
    # Envolvemos em try/except para que, se o LocalStack não estiver acessível, o pipeline
    # ainda conclua a parte local sem quebrar.
    try:
        aws = AWSManager(
            endpoint_url=config.localstack_endpoint,
            region_name=config.aws_region,
        )

        # Garante que bucket, tabela, fila e tópico existam.
        aws.criar_bucket(config.s3_bucket)
        aws.criar_tabela_incidentes(config.dynamodb_table)
        queue_url = aws.criar_fila(config.sqs_queue_name)
        topic_arn = aws.criar_topico_alertas(config.sns_topic_name)

        # Salva o relatório completo em JSON no S3 direto da memória.
        s3_key = f"relatorios/{incidente.incidente_id}.json"
        relatorio_json = json.dumps(
            {
                "incidente_id": incidente.incidente_id,
                "equipamento": incidente.equipamento,
                "severidade": incidente.severidade,
                "diagnostico": incidente.diagnostico,
                "comando_remediacao": incidente.comando_remediacao,
            },
            ensure_ascii=False,
            indent=2,
        )
        if aws.enviar_conteudo_texto(
            conteudo=relatorio_json,
            bucket_name=config.s3_bucket,
            object_name=s3_key,
            content_type="application/json",
        ):
            incidente.s3_key = s3_key

        # Registra o incidente no DynamoDB vinculado ao s3_key.
        aws.registrar_incidente(
            table_name=config.dynamodb_table,
            incidente_id=incidente.incidente_id,
            equipamento=incidente.equipamento,
            severidade=incidente.severidade,
            diagnostico_ia=incidente.diagnostico,
            s3_key=incidente.s3_key or "",
            status=incidente.status,
        )

        # Enfileira no SQS e dispara alerta crítico no SNS se severidade for ALTA ou CRITICA.
        if queue_url:
            aws.enviar_alerta_fila(
                queue_url,
                {
                    "incidente_id": incidente.incidente_id,
                    "equipamento": incidente.equipamento,
                    "severidade": incidente.severidade,
                    "s3_key": incidente.s3_key,
                },
            )

        severidade_normalizada = incidente.severidade.strip().upper()
        if topic_arn and severidade_normalizada in ("ALTA", "CRITICA"):
            aws.disparar_alerta_critico(
                topic_arn=topic_arn,
                assunto=f"[{severidade_normalizada}] {incidente.equipamento} - {incidente.incidente_id}",
                mensagem=f"Diagnóstico: {incidente.diagnostico}\nComando sugerido: {incidente.comando_remediacao}",
            )
        else:
            logger.info(
                f"Notificação SNS não disparada (severidade='{severidade_normalizada}'; "
                "alerta crítico configurado apenas para ALTA/CRITICA)."
            )
    except Exception as exc:
        logger.warning(f"Integração AWS/LocalStack não concluída nesta execução: {exc}")

    # 8. Aplica a remediação através do driver e sincroniza o status 'REMEDIADO' no DynamoDB.
    if driver.aplicar_remediacao(incidente.comando_remediacao):
        incidente.status = "REMEDIADO"
        if aws is not None:
            try:
                aws.atualizar_status_incidente(
                    table_name=config.dynamodb_table,
                    incidente_id=incidente.incidente_id,
                    novo_status=incidente.status,
                )
            except Exception as exc:
                logger.warning(
                    f"Não foi possível sincronizar status '{incidente.status}' no DynamoDB "
                    f"para {incidente.incidente_id}: {exc}"
                )
        logger.info(f"Incidente {incidente.incidente_id} finalizado com status: {incidente.status}")

    return incidente


if __name__ == "__main__":
    configurar_logging()
    incidente_final = executar_pipeline(tipo_driver="simulador")
    print(f"\nResumo final: {incidente_final}")