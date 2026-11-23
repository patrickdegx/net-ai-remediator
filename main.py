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
    # Obtém o logger específico do pipeline principal.
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
    # Recupera o nome do equipamento do driver (com fallback para o padrão).
    equipamento = getattr(driver, "nome_equipamento", "router-borda-sp01")

    # 3.1 Coleta saída de CLI estruturada via TextFSM (quando o driver suportar o método).
    cli_estruturada = None
    dados_cli_parseados = []
    # Verifica com hasattr se o driver instanciado implementa coletar_cli_estruturada (ex.: simulador).
    if hasattr(driver, "coletar_cli_estruturada") and callable(driver.coletar_cli_estruturada):
        try:
            # Chama o método do driver para obter saída bruta e dados parseados pelo NetworkParser.
            cli_estruturada = driver.coletar_cli_estruturada()
            # Garante que seja uma lista caso o retorno venha em outro formato ou None.
            dados_cli_parseados = cli_estruturada.get("parsed_data") or []
        except Exception as exc:
            # Não derruba o pipeline se o parsing estruturado falhar; segue com o log bruto.
            logger.warning(f"Falha ao coletar/parsear CLI estruturada: {exc}")

    # 3.2 Monta o contexto combinado (log bruto + saída/dados estruturados da CLI em JSON) para a IA.
    if dados_cli_parseados:
        # Converte a lista de dicionários do TextFSM para JSON legível, preservando acentos.
        cli_json_formatado = json.dumps(dados_cli_parseados, ensure_ascii=False, indent=2)
        # Monta o texto final unindo o log do evento e os registros estruturados da CLI.
        contexto_analise_ia = (
            f"{log_bruto}\n\n"
            f"[SAÍDA CLI ESTRUTURADA - TEXTFSM (JSON)]\n{cli_json_formatado}"
        )
    elif cli_estruturada and cli_estruturada.get("raw_output"):
        # Fallback: se não houve registros parseados, envia o log bruto junto da saída bruta da CLI.
        contexto_analise_ia = (
            f"{log_bruto}\n\n"
            f"[SAÍDA CLI BRUTA ({cli_estruturada.get('comando', 'CLI')})]\n{cli_estruturada['raw_output']}"
        )
    else:
        # Se o driver não tiver saída de CLI adicional, mantém apenas o log bruto coletado.
        contexto_analise_ia = log_bruto

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

    # 5. Conecta ao LocalStack/AWS (se disponível), busca histórico RAG e roda a análise da IA.
    aws = None
    queue_url = None
    topic_arn = None
    historico_recente = None

    try:
        # Inicializa o cliente AWS apontando para o endpoint configurado (LocalStack ou AWS real).
        aws = AWSManager(
            endpoint_url=config.localstack_endpoint,
            region_name=config.aws_region,
        )
        # Garante que a tabela de incidentes exista antes de consultar o histórico.
        aws.criar_tabela_incidentes(config.dynamodb_table)
        # Busca os últimos incidentes do mesmo equipamento para dar contexto RAG à IA.
        historico_recente = aws.buscar_historico_equipamento(
            table_name=config.dynamodb_table,
            equipamento=incidente.equipamento,
            limite=5,
        )
    except Exception as exc:
        logger.warning(f"Consulta de histórico no DynamoDB não concluída nesta execução: {exc}")

    # Instancia o analisador de IA com o modelo e URL do Ollama configurados.
    analyzer = NetworkAIAnalyzer(
        modelo=config.ollama_model,
        ollama_url=config.ollama_url,
    )
    # Envia o contexto combinado (log + CLI estruturada) junto com o histórico para análise.
    resultado_ia = analyzer.analisar_log_rede(
        log_bruto=contexto_analise_ia,
        equipamento=incidente.equipamento,
        historico_recente=historico_recente or None,
    )

    # 6. Preenche a dataclass DiagnosticoIA e atualiza o IncidenteRede.
    diagnostico_obj = DiagnosticoIA(
        diagnostico=resultado_ia.get("diagnostico", "Sem diagnóstico detalhado."),
        severidade=resultado_ia.get("severidade", "MEDIA"),
        comando_remediacao=resultado_ia.get("comando_remediacao", "show logging"),
    )

    # Transfere os campos validados do diagnóstico para o objeto principal do incidente.
    incidente.diagnostico = diagnostico_obj.diagnostico
    incidente.severidade = diagnostico_obj.severidade
    incidente.comando_remediacao = diagnostico_obj.comando_remediacao
    incidente.status = "ANALISADO"

    # 7. Persiste relatório/incidente e publica eventos no LocalStack / AWS (S3, DynamoDB, SQS, SNS).
    # Envolvemos em try/except para que, se o LocalStack não estiver acessível, o pipeline
    # ainda conclua a parte local sem quebrar.
    if aws is not None:
        try:
            # Garante que bucket S3, fila SQS e tópico SNS existam antes de publicar.
            aws.criar_bucket(config.s3_bucket)
            queue_url = aws.criar_fila(config.sqs_queue_name)
            topic_arn = aws.criar_topico_alertas(config.sns_topic_name)

            # Monta o dicionário base do relatório JSON que será gravado no S3.
            payload_relatorio = {
                "incidente_id": incidente.incidente_id,
                "equipamento": incidente.equipamento,
                "severidade": incidente.severidade,
                "diagnostico": incidente.diagnostico,
                "comando_remediacao": incidente.comando_remediacao,
            }
            # Se houver dados parseados pelo TextFSM, inclui também no JSON enviado ao S3.
            if dados_cli_parseados:
                payload_relatorio["cli_estruturada"] = dados_cli_parseados

            # Salva o relatório completo em JSON no S3 direto da memória.
            s3_key = f"relatorios/{incidente.incidente_id}.json"
            relatorio_json = json.dumps(
                payload_relatorio,
                ensure_ascii=False,
                indent=2,
            )
            # Envia o JSON para o S3 e guarda a chave do objeto no incidente se der certo.
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

            # Enfileira no SQS um resumo do incidente para consumidores assíncronos.
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

            # Normaliza a severidade para disparar alerta crítico no SNS apenas em ALTA ou CRITICA.
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
    # Ponto de entrada quando o arquivo é executado diretamente.
    configurar_logging()
    incidente_final = executar_pipeline(tipo_driver="simulador")
    print(f"\nResumo final: {incidente_final}")