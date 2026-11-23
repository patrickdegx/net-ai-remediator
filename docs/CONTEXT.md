# Contexto do Projeto: Net-AI Remediator (Portfólio DevOps & Redes)

## 1. Objetivo do Projeto
Desenvolver uma ferramenta autônoma de monitoramento, diagnóstico e remediação de rede e nuvem para portfólio profissional focado em vagas de **DevOps / Engenharia de Redes**. O projeto demonstra domínio de infraestrutura híbrida (On-Premises + Cloud), automação em Python com Programação Orientada a Objetos (POO) e análise inteligente de logs utilizando Inteligência Artificial local.

## 2. Arquitetura Híbrida (On-Premises + Cloud + IA)
- **Camada On-Premises / Rede:** Simulador de roteador (`SimuladorRoteadorDriver`), driver SSH com `NetmikoRouterDriver` (incluindo retry com backoff exponencial, validação de rede de gerência e integração com Secrets Manager), parsing estruturado de CLI via `TextFSM` (`NetworkParser`) e gatilhos de eventos em tempo real via Webhook HTTP e UDP Syslog (`src/triggers/event_trigger.py`).
- **Camada Cloud (AWS / LocalStack):** Uso do **Docker** + **LocalStack** para emular localmente serviços da AWS (`S3`, `DynamoDB`, `Secrets Manager`, `SQS` e `SNS`) na região `us-east-1`, com suporte a configuração de ambiente via `AppConfig` e `AWSManager`.
- **Camada de Inteligência & Remediação (IA Local):** Execução de LLMs localmente via **Ollama** (`NetworkAIAnalyzer`, ex.: `llama3`) para analisar logs/saídas de CLI, consultar histórico recente de incidentes no DynamoDB (RAG), validar comandos e sugerir ações de remediação.

## 3. Padrões de Engenharia e Estrutura de Pastas
- **Linguagem:** Python 3 (modularizado e orientado a objetos).
- **Padrões e Módulos Principais:**
  * **Factory Pattern (`src/network/drivers.py`):** `NetworkDriverFactory` instancia drivers de rede (`simulador` ou `netmiko`).
  * **Gatilhos de Eventos (`src/triggers/event_trigger.py`):** `WebhookEventServer` e `SyslogUDPServer` normalizam eventos e alimentam o pipeline no `main.py`.
- **Árvore de Diretórios (`net-ai-remediator`):**
  ```text
  net-ai-remediator/
  ??? docs/                 # Documentação e CONTEXT.md
  ??? infra/                # Arquivos de infraestrutura (docker-compose.yml)
  ??? logs/                 # Armazenamento local de logs para testes
  ??? src/                  # Código-fonte principal (pacotes Python com __init__.py)
  ?   ??? ai/               # analyzer.py (Análise via Ollama e validação de comandos)
  ?   ??? cloud/            # aws_client.py (Integração AWS / LocalStack)
  ?   ??? core/             # config.py e models.py (Configurações e dataclasses)
  ?   ??? network/          # drivers.py, parser.py e templates TextFSM
  ?   ??? triggers/         # event_trigger.py (Webhook HTTP e Syslog UDP)
  ??? tests/                # Scripts de teste e validação
  ??? main.py               # Ponto de entrada e orquestração do pipeline
  ??? requirements.txt      # Dependências Python
  ??? README.md             # Documentação do repositório




  Contexto do Projeto: Net-AI Remediator
Data da Atualização: 16/11/2026

Status Atual: Camada Cloud AWS (S3, DynamoDB, Secrets Manager, SQS e SNS) implementada e validada localmente via LocalStack.

1. Infraestrutura & Docker (infra/docker-compose.yml)
Localização do Arquivo: infra/docker-compose.yml (execução via docker-compose -f infra/docker-compose.yml up -d).

Imagem Utilizada: localstack/localstack:3.8.1 (versão Community estável).

Nota Técnica: Evitar a tag :latest, pois versões mais recentes podem exigir autenticação/licença Pro (LOCALSTACK_AUTH_TOKEN).

Mapeamento de Rede: Porta configurada como 127.0.0.1:4566:4566 para evitar bloqueios de firewall/rede no Windows.

Serviços Ativos: s3,dynamodb,sns,sqs,secretsmanager na região padrão us-east-1.

2. Módulo Cloud (src/cloud/aws_client.py)
A classe AWSManager foi implementada com suporte ao ciclo de vida de objetos no S3:

Configuração de Cliente: Uso de botocore.config.Config com s3={'addressing_style': 'path'} para compatibilidade de resolução de URLs locais no Windows (http://localhost:4566/<bucket>).

Métodos Implementados (Base S3):

criar_bucket(bucket_name): Cria buckets S3.

listar_buckets(): Lista os buckets disponíveis.

enviar_arquivo(file_name, bucket_name, object_name, metadata=None): Faz upload de arquivos locais para o S3, com suporte opcional a metadados via ExtraArgs.

baixar_arquivo(bucket_name, object_name, file_name): Baixa objetos do S3 para o sistema local.

deletar_arquivo(bucket_name, object_name): Remove objetos específicos de dentro do bucket.

gerar_url_presassinada(bucket_name, object_name, expiration=3600): Gera URLs temporárias e assinadas para acesso controlado a objetos.

3. Validação & Conceitos Estudados (tests/teste_aws_16_11_26.py)
Fluxo de Teste Integrado: Script executado validando criação de bucket, listagem, upload de arquivo de log, download, geração de URL pré-assinada e deleção do objeto.

Validação de Comportamento S3 (NoSuchKey): Ao acessar a URL pré-assinada após a remoção do objeto, o LocalStack retornou NoSuchKey, confirmando a validação da assinatura da URL e a exclusão prévia do arquivo.

Formas de Inspeção do LocalStack:

Via AWS CLI: aws --endpoint-url=http://localhost:4566 s3 ls

Via Healthcheck HTTP: http://localhost:4566/_localstack/health

Via código Python (s3_client.list_objects_v2).

4. Atualizações Finais (Sessão Noturna — 16/11/2026)
4.1. Engenharia de Software e Expansão LocalStack
Refatoração Estrutural: Uso do módulo logging, adição de Type Hints nos métodos e tratamento específico de botocore.exceptions.ClientError.

Expansão de Serviços (infra/docker-compose.yml): Variável SERVICES configurada para s3,dynamodb,sns,sqs,secretsmanager, com retries={'max_attempts': 3, 'mode': 'standard'} no Config.

4.2. Evoluções Avançadas no S3 (self.s3_client)
enviar_conteudo_texto(conteudo, bucket_name, object_name, metadata=None, content_type="text/plain; charset=utf-8"): Grava strings (logs, JSONs, relatórios) direto da memória via put_object.

ler_conteudo_texto(bucket_name, object_name): Lê e decodifica objetos do S3 para memória via get_object.

listar_arquivos(bucket_name, prefixo=""): Lista chaves filtradas por prefixo (list_objects_v2).

arquivo_existe(bucket_name, object_name): Verifica existência via head_object, tratando 404 / NoSuchKey.

obter_metadados(bucket_name, object_name): Recupera metadados do objeto via head_object.

definir_tags(bucket_name, object_name, tags): Aplica ou atualiza tags via put_object_tagging.

obter_tags(bucket_name, object_name): Lê tags associadas ao objeto via get_object_tagging.

4.3. Módulo DynamoDB (self.dynamodb_client & tests/teste_dynamodb.py)
criar_tabela_incidentes(table_name="net-ai-incidentes"): Cria tabela com Partition Key incidente_id (S) e BillingMode='PAY_PER_REQUEST', tratando ResourceInUseException.

registrar_incidente(table_name, incidente_id, equipamento, severidade, diagnostico_ia, s3_key, status="PENDENTE"): Insere registro estruturado via put_item.

buscar_incidente(table_name, incidente_id): Consulta por chave primária via get_item e converte para dicionário Python.

atualizar_status_incidente(table_name, incidente_id, novo_status): Atualiza o campo status via update_item usando ExpressionAttributeNames (#st).

5. Atualizações de Mensageria e Cofre (17/11/2026)
5.1. Módulo Secrets Manager (self.secrets_client & tests/teste_secrets.py)
criar_segredo(nome_segredo, segredo_dict, descricao=""): Cria segredo em JSON via create_secret, tratando ResourceExistsException.

buscar_segredo(nome_segredo): Recupera segredo via get_secret_value e retorna dicionário Python.

atualizar_segredo(nome_segredo, novos_dados_dict): Atualiza segredo existente via put_secret_value.

5.2. Módulo SQS (self.sqs_client & tests/teste_sqs.py)
criar_fila(nome_fila="net-ai-alertas-queue"): Cria fila via create_queue e retorna QueueUrl.

enviar_alerta_fila(queue_url, evento_dict): Publica mensagem JSON na fila via send_message.

consumir_alertas_fila(queue_url, max_mensagens=5): Lê mensagens com Long Polling (WaitTimeSeconds=2) e remove mensagens processadas via delete_message.

5.3. Módulo SNS (self.sns_client & tests/teste_sns.py)
criar_topico_alertas(nome_topico="net-ai-alertas-criticos"): Cria tópico via create_topic e retorna TopicArn.

inscrever_alerta(topic_arn, protocolo, endpoint): Inscreve endpoint no tópico via subscribe.

disparar_alerta_critico(topic_arn, assunto, mensagem): Publica alerta via publish limitando o assunto a 100 caracteres (assunto[:100]).

Contexto do Projeto: Net-AI Remediator
Data da Última Atualização: 17 de Novembro de 2026

1. Resumo do Progresso
Foco na análise de logs via IA (NetworkAIAnalyzer), validação de comandos de remediação e injeção de histórico de incidentes (RAG) com persistência no DynamoDB.

2. Componentes Desenvolvidos e Atualizados
Camada de IA & Segurança (src/ai/analyzer.py):

Integração local com Ollama (llama3 via API configurável).

Respostas determinísticas com "temperature": 0.0.

Validação de comandos (_validar_comando_seguro) bloqueando comandos destrutivos perigosos e permitindo comandos de diagnóstico seguros com filtros.

Injeção de histórico recente de incidentes do DynamoDB no contexto de análise (RAG).

Camada de Rede (src/network/drivers.py):

Interface base NetworkDriverInterface e SimuladorRoteadorDriver para simulação de coleta de logs e aplicação de remediação, além de NetmikoRouterDriver e NetworkDriverFactory.

Contexto do Projeto: Net-AI Remediator
Data da Última Atualização: 18 de Novembro de 2026

Status do Projeto: Evolução da camada de rede, parsing estruturado, resiliência e gatilhos de eventos

1. O Que Já Foi Concluído
Camada de IA & Segurança (src/ai/analyzer.py): Integração com Ollama, temperature: 0.0, validação de comandos de remediação e suporte a histórico recente (RAG).

Infraestrutura Cloud (LocalStack): S3, DynamoDB, Secrets Manager, SQS e SNS implementados no AWSManager.

Camada de Rede (src/network/drivers.py): NetworkDriverInterface, SimuladorRoteadorDriver, NetmikoRouterDriver e NetworkDriverFactory.

2. Pilares do Roadmap
[Pilar 1] Acesso Real via SSH (Netmiko): NetmikoRouterDriver com validação de rede de gerência e busca de credenciais no Secrets Manager.

[Pilar 2] Resiliência e Tratamento de Erros: Retry com backoff exponencial e tratamento de timeout/autenticação no NetmikoRouterDriver.

[Pilar 3] Parsing Estruturado de CLI (TextFSM): NetworkParser e coletar_cli_estruturada() integrados ao pipeline e ao relatório JSON no S3.

[Pilar 4] Gatilhos de Eventos em Tempo Real (Webhook / Syslog): WebhookEventServer e SyslogUDPServer em src/triggers/event_trigger.py integrados ao main.py (--webhook, --syslog e _processar_evento_gatilho).

Atualização — 22/11/2026
Contexto do Projeto: Net-AI Remediator
Data da Última Atualização: 22 de Novembro de 2026

Status do Projeto: Pipeline Principal Integrado com LocalStack, Ollama (llama3) e Sincronização de Estado no DynamoDB

Configuração centralizada (src/core/config.py): Implementação de AppConfig (@dataclass(frozen=True)) lendo variáveis de ambiente (LOCALSTACK_HOST, AWS_DEFAULT_REGION, OLLAMA_MODEL, OLLAMA_URL), definindo padrões para bucket S3, tabela DynamoDB, fila SQS e tópico SNS, e expondo localstack_endpoint.

Modelos de domínio (src/core/models.py): Formalização das estruturas IncidenteRede e DiagnosticoIA com @dataclass.

Padronização de logging (src/cloud/aws_client.py): Remoção de logging.basicConfig(...) do módulo para centralizar a configuração de logs no ponto de entrada (main.py).

Orquestração e sincronização de estado (main.py): Integração do fluxo com driver via factory, modelos, NetworkAIAnalyzer e AWSManager (S3, DynamoDB, SQS, SNS), incluindo log quando o SNS não dispara fora de severidades ALTA ou CRITICA e atualização do status do incidente no DynamoDB para REMEDIADO quando aplicar_remediacao(...) retorna True.

Ajustes de rede, IA e higiene de Git: Refinamentos em src/ai/analyzer.py e src/network/drivers.py, atualização do .gitignore e remoção de arquivos .pyc rastreados no índice.

Atualização — 23/11/2026
Histórico recente no DynamoDB para RAG (src/cloud/aws_client.py): Implementação do método buscar_historico_equipamento para recuperar incidentes anteriores de um equipamento e alimentar o contexto histórico da IA.

Integração do histórico antes da análise (main.py): Ajuste do fluxo para consultar e repassar historico_recente a analyzer.analisar_log_rede(...) antes da análise do log.

Teste de validação (tests/teste_rag_historico.py): Criação e execução do teste validando registro e consulta do histórico de incidentes no DynamoDB via LocalStack.