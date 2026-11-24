import argparse
import json
import logging
import os
import uuid
from datetime import datetime
from typing import Any, Dict, Optional

# Importações dos módulos internos do projeto (IA, nuvem AWS/LocalStack, configuração, modelos, drivers e gatilhos).
from src.ai.analyzer import NetworkAIAnalyzer
from src.cloud.aws_client import AWSManager
from src.core.config import AppConfig
from src.core.models import DiagnosticoIA, IncidenteRede
from src.network.drivers import NetworkDriverFactory
from src.triggers.event_trigger import SyslogUDPServer, WebhookEventServer


def configurar_logging() -> None:
    # Configura o formato e o nível global de logs apenas no ponto de entrada da aplicação.
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def _instancia_aws_manager(config: AppConfig) -> Optional[AWSManager]:
    # Tenta criar o cliente AWS/LocalStack e garantir a tabela de incidentes para RAG/auditoria.
    try:
        aws = AWSManager(
            endpoint_url=config.localstack_endpoint,
            region_name=config.aws_region,
        )
        aws.criar_tabela_incidentes(config.dynamodb_table)
        return aws
    except Exception as exc:
        logger = logging.getLogger("MainPipeline")
        logger.warning(f"AWSManager indisponível nesta execução: {exc}")
        return None


def executar_pipeline(
    tipo_driver: str = "simulador",
    log_bruto_externo: Optional[str] = None,
    equipamento_externo: Optional[str] = None,
    ip_equipamento: Optional[str] = None,
    device_type: str = "cisco_ios",
    secret_name: Optional[str] = None,
    aws_manager: Optional[AWSManager] = None,
) -> IncidenteRede:
    # Cria o logger específico da orquestração principal.
    logger = logging.getLogger("MainPipeline")

    # Carrega as configurações centralizadas (endpoints, nomes de recursos AWS e parâmetros do Ollama).
    config = AppConfig()
    logger.info(f"Iniciando pipeline | Endpoint LocalStack: {config.localstack_endpoint}")

    # Inicializa AWSManager se não tiver sido injetado externamente, para uso em RAG e/ou Secrets Manager.
    aws: Optional[AWSManager] = aws_manager if aws_manager is not None else _instancia_aws_manager(config)

    # Define o nome inicial do equipamento priorizando o valor recebido por evento externo, se houver.
    nome_eq_inicial = (equipamento_externo or "router-borda-sp01").strip() or "router-borda-sp01"

    # Instancia o driver de rede escolhido via Factory, repassando parâmetros específicos do Netmiko.
    driver_normalizado = tipo_driver.strip().lower()
    if driver_normalizado == "netmiko":
        segredo_resolvido = secret_name or os.getenv("ROUTER_SECRET_NAME")
        driver = NetworkDriverFactory.criar_driver(
            tipo_driver,
            nome_equipamento=nome_eq_inicial,
            ip=ip_equipamento,
            device_type=device_type,
            secret_name=segredo_resolvido,
            aws_manager=aws,
        )
    else:
        driver = NetworkDriverFactory.criar_driver(
            tipo_driver,
            nome_equipamento=nome_eq_inicial,
        )

    # Usa o log vindo de gatilho externo (Webhook/Syslog) se informado; caso contrário, coleta do driver.
    if log_bruto_externo and log_bruto_externo.strip():
        log_bruto = log_bruto_externo.strip()
        equipamento = nome_eq_inicial
    else:
        log_bruto = driver.coletar_logs_recentes()
        equipamento = getattr(driver, "nome_equipamento", nome_eq_inicial)

    # Tenta coletar saída de CLI estruturada via TextFSM caso o driver implemente esse recurso.
    cli_estruturada = None
    dados_cli_parseados = []
    if hasattr(driver, "coletar_cli_estruturada") and callable(driver.coletar_cli_estruturada):
        try:
            cli_estruturada = driver.coletar_cli_estruturada()
            dados_cli_parseados = cli_estruturada.get("parsed_data") or []
        except Exception as exc:
            # Registra aviso sem interromper o pipeline caso a coleta/parsing estruturado falhe.
            logger.warning(f"Falha ao coletar/parsear CLI estruturada: {exc}")

    # Combina o log bruto com os dados parseados em JSON (ou saída bruta de CLI) para enviar à IA.
    if dados_cli_parseados:
        cli_json_formatado = json.dumps(dados_cli_parseados, ensure_ascii=False, indent=2)
        contexto_analise_ia = (
            f"{log_bruto}\n\n"
            f"[SAÍDA CLI ESTRUTURADA - TEXTFSM (JSON)]\n{cli_json_formatado}"
        )
    elif cli_estruturada and cli_estruturada.get("raw_output"):
        contexto_analise_ia = (
            f"{log_bruto}\n\n"
            f"[SAÍDA CLI BRUTA ({cli_estruturada.get('comando', 'CLI')})]\n{cli_estruturada['raw_output']}"
        )
    else:
        contexto_analise_ia = log_bruto

    # Gera um identificador único com data/hora local e cria a entidade inicial IncidenteRede.
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

    # Busca incidentes anteriores do mesmo equipamento para contexto RAG caso a conexão AWS esteja ativa.
    queue_url = None
    topic_arn = None
    historico_recente = None

    if aws is not None:
        try:
            historico_recente = aws.buscar_historico_equipamento(
                table_name=config.dynamodb_table,
                equipamento=incidente.equipamento,
                limite=5,
            )
        except Exception as exc:
            # Se o DynamoDB/LocalStack não estiver acessível, segue a execução sem histórico prévio.
            logger.warning(f"Consulta de histórico no DynamoDB não concluída nesta execução: {exc}")

    # Instancia o analisador de IA (Ollama) e executa o diagnóstico usando o log e o histórico RAG.
    analyzer = NetworkAIAnalyzer(
        modelo=config.ollama_model,
        ollama_url=config.ollama_url,
    )
    resultado_ia = analyzer.analisar_log_rede(
        log_bruto=contexto_analise_ia,
        equipamento=incidente.equipamento,
        historico_recente=historico_recente or None,
    )

    # Estrutura o retorno da IA em DiagnosticoIA e atualiza os campos e o status do IncidenteRede.
    diagnostico_obj = DiagnosticoIA(
        diagnostico=resultado_ia.get("diagnostico", "Sem diagnóstico detalhado."),
        severidade=resultado_ia.get("severidade", "MEDIA"),
        comando_remediacao=resultado_ia.get("comando_remediacao", "show logging"),
    )

    incidente.diagnostico = diagnostico_obj.diagnostico
    incidente.severidade = diagnostico_obj.severidade
    incidente.comando_remediacao = diagnostico_obj.comando_remediacao
    incidente.status = "ANALISADO"

    # Persiste relatório no S3, grava registro no DynamoDB, publica no SQS e dispara alerta SNS se crítico/alto.
    if aws is not None:
        try:
            # Garante que os recursos básicos (bucket, fila e tópico) existam antes de publicar.
            aws.criar_bucket(config.s3_bucket)
            queue_url = aws.criar_fila(config.sqs_queue_name)
            topic_arn = aws.criar_topico_alertas(config.sns_topic_name)

            # Monta o JSON do relatório do incidente, anexando os dados estruturados do TextFSM quando existirem.
            payload_relatorio = {
                "incidente_id": incidente.incidente_id,
                "equipamento": incidente.equipamento,
                "severidade": incidente.severidade,
                "diagnostico": incidente.diagnostico,
                "comando_remediacao": incidente.comando_remediacao,
            }
            if dados_cli_parseados:
                payload_relatorio["cli_estruturada"] = dados_cli_parseados

            # Envia o relatório JSON para o S3 e salva a chave (s3_key) no incidente se o envio tiver sucesso.
            s3_key = f"relatorios/{incidente.incidente_id}.json"
            relatorio_json = json.dumps(
                payload_relatorio,
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

            # Registra o incidente na tabela do DynamoDB apontando para o relatório no S3.
            aws.registrar_incidente(
                table_name=config.dynamodb_table,
                incidente_id=incidente.incidente_id,
                equipamento=incidente.equipamento,
                severidade=incidente.severidade,
                diagnostico_ia=incidente.diagnostico,
                s3_key=incidente.s3_key or "",
                status=incidente.status,
            )

            # Publica um resumo do incidente na fila SQS para processamento assíncrono.
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

            # Dispara notificação no tópico SNS apenas quando a severidade for ALTA ou CRITICA.
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
            # Evita que falhas de conectividade com o LocalStack/AWS quebrem o restante do fluxo.
            logger.warning(f"Integração AWS/LocalStack não concluída nesta execução: {exc}")

    # Executa a remediação sugerida no driver e sincroniza o status 'REMEDIADO' no DynamoDB se aplicado.
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

    # Retorna o objeto IncidenteRede com o estado final do processamento.
    return incidente


def _processar_evento_gatilho(
    evento: Dict[str, Any],
    tipo_driver: str = "simulador",
    ip_equipamento: Optional[str] = None,
    device_type: str = "cisco_ios",
    secret_name: Optional[str] = None,
) -> IncidenteRede:
    # Adapta o dicionário de evento recebido pelo gatilho para os parâmetros do executar_pipeline.
    return executar_pipeline(
        tipo_driver=tipo_driver,
        log_bruto_externo=evento.get("log_bruto"),
        equipamento_externo=evento.get("equipamento"),
        ip_equipamento=evento.get("ip") or ip_equipamento,
        device_type=evento.get("device_type") or device_type,
        secret_name=evento.get("secret_name") or secret_name,
    )


def _parse_args() -> argparse.Namespace:
    # Configura os argumentos de linha de comando para rodar o pipeline ou escutar Webhook/Syslog.
    parser = argparse.ArgumentParser(description="Net-AI Remediator Pipeline")
    parser.add_argument(
        "--driver",
        default="simulador",
        help="Tipo de driver de rede (padrão: simulador)",
    )
    parser.add_argument(
        "--ip",
        default=os.getenv("ROUTER_IP"),
        help="Endereço IP de gerência do equipamento (usado no driver netmiko)",
    )
    parser.add_argument(
        "--device-type",
        default=os.getenv("ROUTER_DEVICE_TYPE", "cisco_ios"),
        help="Tipo de dispositivo Netmiko (padrão: cisco_ios)",
    )
    parser.add_argument(
        "--secret-name",
        default=os.getenv("ROUTER_SECRET_NAME"),
        help="Nome do segredo no AWS Secrets Manager (ou via ROUTER_SECRET_NAME)",
    )
    parser.add_argument(
        "--webhook",
        action="store_true",
        help="Inicia servidor HTTP Webhook para receber eventos em tempo real",
    )
    parser.add_argument(
        "--syslog",
        action="store_true",
        help="Inicia listener UDP Syslog para receber eventos em tempo real",
    )
    parser.add_argument(
        "--webhook-port",
        type=int,
        default=int(os.getenv("WEBHOOK_PORT", "8080")),
        help="Porta do servidor Webhook HTTP (padrão: 8080)",
    )
    parser.add_argument(
        "--syslog-port",
        type=int,
        default=int(os.getenv("SYSLOG_PORT", "1514")),
        help="Porta do listener UDP Syslog (padrão: 1514)",
    )
    return parser.parse_args()


if __name__ == "__main__":
    # Inicializa os logs, lê os argumentos CLI e dispara o modo escolhido (webhook, syslog ou execução direta).
    configurar_logging()
    args = _parse_args()

    if args.webhook:
        servidor_http = WebhookEventServer(
            port=args.webhook_port,
            callback_evento=lambda ev: _processar_evento_gatilho(
                ev,
                tipo_driver=args.driver,
                ip_equipamento=args.ip,
                device_type=args.device_type,
                secret_name=args.secret_name,
            ),
        )
        servidor_http.iniciar(bloqueante=True)
    elif args.syslog:
        servidor_syslog = SyslogUDPServer(
            port=args.syslog_port,
            callback_evento=lambda ev: _processar_evento_gatilho(
                ev,
                tipo_driver=args.driver,
                ip_equipamento=args.ip,
                device_type=args.device_type,
                secret_name=args.secret_name,
            ),
        )
        servidor_syslog.iniciar(bloqueante=True)
    else:
        incidente_final = executar_pipeline(
            tipo_driver=args.driver,
            ip_equipamento=args.ip,
            device_type=args.device_type,
            secret_name=args.secret_name,
        )
        print(f"\nResumo final: {incidente_final}")[cite: 3]