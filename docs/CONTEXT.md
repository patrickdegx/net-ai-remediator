# Contexto do Projeto: Net-AI Remediator (Portfólio DevOps & Redes)

## 1. Objetivo do Projeto
Desenvolver uma ferramenta autônoma de monitoramento, diagnóstico e remediação de rede e nuvem para portfólio profissional focado em vagas de **DevOps / Engenharia de Redes**. O projeto demonstra domínio de infraestrutura híbrida (On-Premises + Cloud), automação em Python com Programação Orientada a Objetos (POO) e análise inteligente de logs utilizando Inteligência Artificial local.

## 2. Arquitetura Híbrida (On-Premises + Cloud + IA)
- **Camada On-Premises / Rede:** Roteadores simulados via containers Linux (**FRRouting / FRR**) e integração futura via rede *Bridge/Host-Only* com máquinas virtuais reais no **VMware / EVE-NG** (ex: **MikroTik RouterOS**).
- **Camada Cloud (AWS Simulada):** Uso do **Docker** + **LocalStack** para emular serviços da AWS localmente (S3, EC2, IAM, CloudWatch Logs) sem custos financeiros.
- **Camada de Inteligência & Remediação (IA Local):** Execução de LLMs localmente via **Ollama** para ler logs de rede/sistema, diagnosticar falhas e sugerir comandos de correção.

## 3. Padrões de Engenharia e Estrutura de Pastas
- **Linguagem:** Python 3 (modularizado e orientado a objetos).
- **Design Patterns:**
  * **Factory Pattern (`src/network`):** Instancia drivers de conexão (SSH/API) dinamicamente por fabricante (FRR, MikroTik, etc.).
  * **Strategy Pattern (`src/ai`):** Permite alternar o motor de IA (Ollama local, APIs externas, etc.) sem alterar o restante do código.
- **Ýrvore de Diretórios Criada (`~/net-ai-remediator`):**
  ```text
  net-ai-remediator/
  ├── docs/               # Documentação e CONTEXT.md (Save Game do projeto)
  ├── infra/              # Arquivos de infraestrutura (docker-compose.yml)
  ├── logs/               # Armazenamento local de logs para testes
  ├── src/                # Código-fonte principal (pacotes Python com __init__.py)
  │   ├── ai/             # analyzer.py (Integração com IA)
  │   ├── cloud/          # aws_client.py (Integração AWS / LocalStack)
  │   ├── core/           # config.py (Configurações globais)
  │   └── network/        # drivers.py (Conexões SSH e parsers)
  ├── tests/              # Testes unitários e de integração
  │   ├── teste_aws_16_11_26.py  # Testes de integração S3 (básico e avançado)
  │   ├── teste_dynamodb.py      # Testes de integração DynamoDB
  │   ├── teste_secrets.py       # Testes de integração Secrets Manager
  │   ├── teste_sqs.py           # Testes de integração SQS
  │   └── teste_sns.py           # Testes de integração SNS
  ├── main.py             # Ponto de entrada da aplicação
  ├── requirements.txt    # Dependências Python
  └── README.md           # Apresentação do projeto no GitHub


  Contexto do Projeto: Net-AI Remediator
Data da Atualização: 16/11/2026
Status Atual: Camada Cloud AWS (S3, DynamoDB, Secrets Manager, SQS e SNS) 100% finalizada e validada localmente via LocalStack.

1. Infraestrutura & Docker (infra/docker-compose.yml)
Localização do Arquivo: infra/docker-compose.yml (execução via docker-compose -f infra/docker-compose.yml up -d).

Imagem Utilizada: localstack/localstack:3.8.1 (versão Community estável).

Nota Técnica: Evitar a tag :latest, pois versões mais recentes exigem autenticação/licença Pro (LOCALSTACK_AUTH_TOKEN, retornando exit code 55).

Mapeamento de Rede: Porta configurada explicitamente como 127.0.0.1:4566:4566 para evitar bloqueios de firewall/rede no Windows.

Serviços Ativos: Inicialmente s3 e posteriormente expandido para s3,dynamodb,sns,sqs,secretsmanager na região padrão us-east-1 (container devops_aws_sim).

2. Módulo Cloud (src/cloud/aws_client.py)
A classe AWSManager foi implementada com suporte completo ao ciclo de vida de objetos no S3:

Configuração de Cliente: Uso de botocore.config.Config com s3={'addressing_style': 'path'} para garantir compatibilidade de resolução de URLs locais no Windows (http://localhost:4566/<bucket>).

Métodos Implementados (Etapa 1 - Base S3):

criar_bucket(bucket_name): Cria buckets S3.

listar_buckets(): Lista todos os buckets disponíveis na conta/simulador.

enviar_arquivo(file_name, bucket_name, object_name): Faz upload de arquivos locais para o S3.

baixar_arquivo(bucket_name, object_name, file_name): Realiza o download de objetos do S3 para o sistema local.

deletar_arquivo(bucket_name, object_name): Remove objetos específicos de dentro do bucket (limpeza de logs/temporários).

gerar_url_presassinada(bucket_name, object_name, expiration=3600): Gera links temporários e assinados criptograficamente para acesso seguro e controlado a objetos privados sem expor credenciais.

3. Validação & Conceitos Estudados (tests/teste_aws_16_11_26.py)
Fluxo de Teste Integrado: Script executado com sucesso validando ponta a ponta: criação do bucket net-ai-bucket-teste-2026, listagem, upload de logs/teste_log.txt, download, geração de URL pré-assinada e deleção final do objeto.

Validação de Comportamento S3 (XML NoSuchKey): Ao abrir a URL pré-assinada no navegador após a execução completa do script de teste, o LocalStack retornou o XML padrão da AWS <Code>NoSuchKey</Code>. Isso comprovou na prática que:

A assinatura digital da URL pré-assinada (AWSAccessKeyId + Signature + Expires) foi validada corretamente pelo servidor.

O método deletar_arquivo havia removido o objeto com sucesso logo antes da requisição.

Formas de Inspeção do LocalStack:

Via AWS CLI: aws --endpoint-url=http://localhost:4566 s3 ls

Via Healthcheck HTTP: http://localhost:4566/_localstack/health

Via código Python (s3_client.list_objects_v2).

4. Atualizações Finais (Sessão Noturna - 16/11/2026)
Acréscimos realizados no AWSManager (src/cloud/aws_client.py) e na infraestrutura para elevar o módulo ao padrão de produção:

4.1. Engenharia de Software e Expansão LocalStack
Refatoração Estrutural: Substituição de print() pelo módulo nativo logging (formato com timestamp e níveis [INFO]/[ERROR]), adição de Type Hints em todos os métodos e tratamento específico de botocore.exceptions.ClientError.

Expansão de Serviços (infra/docker-compose.yml): Variável SERVICES atualizada para s3,dynamodb,sns,sqs,secretsmanager, mantendo retries={'max_attempts': 3, 'mode': 'standard'} no Config.

4.2. Evoluções Avançadas no S3 (self.s3_client)
Suporte a Metadados no Upload Físico: enviar_arquivo atualizado para aceitar o parâmetro opcional metadata: Optional[Dict[str, str]] = None via ExtraArgs.

Novos Métodos Implementados:
7. enviar_conteudo_texto(conteudo, bucket_name, object_name, metadata=None, content_type="text/plain; charset=utf-8"): Grava strings (logs brutos, JSONs, relatórios da IA) direto da memória RAM via put_object, evitando arquivos temporários em disco.
8. ler_conteudo_texto(bucket_name, object_name): Lê e decodifica objetos do S3 direto para a memória RAM via get_object.
9. listar_arquivos(bucket_name, prefixo=""): Listagem filtrada por prefixo (list_objects_v2), separando caminhos lógicos (relatorios/ vs logs/).
10. arquivo_existe(bucket_name, object_name): Checagem leve via requisição HEAD (head_object), capturando erros 404/NoSuchKey.
11. obter_metadados(bucket_name, object_name): Lê metadados imutáveis gravados no cabeçalho do objeto.
12. definir_tags(bucket_name, object_name, tags): Aplica/atualiza tags dinâmicas (put_object_tagging) para rastreamento e ciclo de vida.
13. obter_tags(bucket_name, object_name): Recupera tags associadas ao objeto (get_object_tagging).

4.3. Módulo DynamoDB (self.dynamodb_client & tests/teste_dynamodb.py)
Implementação do banco NoSQL para indexar o histórico estruturado dos incidentes de rede e vincular cada ocorrência ao relatório salvo no S3 (s3_key):

Métodos Implementados:

criar_tabela_incidentes(table_name="net-ai-incidentes"): Cria tabela NoSQL com Partition Key incidente_id (S) e BillingMode='PAY_PER_REQUEST', tratando ResourceInUseException caso já exista.

registrar_incidente(table_name, incidente_id, equipamento, severidade, diagnostico_ia, s3_key, status="PENDENTE"): Insere registro estruturado (put_item) vinculando o evento ao arquivo no S3.

buscar_incidente(table_name, incidente_id): Consulta pela chave primária (get_item) e converte o formato tipado do DynamoDB ({'S': 'valor'}) para dicionário Python limpo.

atualizar_status_incidente(table_name, incidente_id, novo_status): Atualiza o estado do incidente (update_item, ex: ANALISADO → REMEDIADO) usando ExpressionAttributeNames (#st) para evitar conflito com a palavra reservada status.

Validação (tests/teste_dynamodb.py): Testado ponta a ponta com sucesso (criação da tabela net-ai-incidentes, registro de INC-2026-001, busca e atualização de status para REMEDIADO).

5. Atualizações de Mensageria e Cofre (17/11/2026)
Conclusão integral da camada Cloud no AWSManager (src/cloud/aws_client.py) com a implementação e validação dos três serviços restantes:

5.1. Módulo Secrets Manager (self.secrets_client & tests/teste_secrets.py)
Cofre de credenciais de automação (máquina para máquina) para evitar exposição de senhas de roteadores e chaves de API no código-fonte/GitHub:

Métodos Implementados:

criar_segredo(nome_segredo, segredo_dict, descricao=""): Grava dicionários de credenciais (host, usuário, senha, porta) convertidos em JSON no cofre (create_secret), tratando ResourceExistsException.

buscar_segredo(nome_segredo): Recupera credenciais diretamente para a memória RAM (get_secret_value) e retorna um dicionário Python limpo.

atualizar_segredo(nome_segredo, novos_dados_dict): Realiza rotação/atualização de credenciais existentes (put_secret_value).

Validação (tests/teste_secrets.py): Testado ciclo completo de criação, leitura e rotação de senha para o segredo net-ai/roteadores/mikrotik-borda.

5.2. Módulo SQS (self.sqs_client & tests/teste_sqs.py)
Fila assíncrona que atua como amortecedor para absorver picos de alertas de rede sem sobrecarregar o motor de IA:

Métodos Implementados:

criar_fila(nome_fila="net-ai-alertas-queue"): Cria a fila no SQS (create_queue) e retorna a QueueUrl.

enviar_alerta_fila(queue_url, evento_dict): Publica tickets de incidentes (dicionários convertidos em JSON) na fila (send_message).

consumir_alertas_fila(queue_url, max_mensagens=5): Lê mensagens usando Long Polling (WaitTimeSeconds=2), converte de volta para dicionário e confirma o processamento removendo cada mensagem via ReceiptHandle (delete_message).

Validação (tests/teste_sqs.py): Testado envio simultâneo de alertas (router-borda-sp01 e switch-core-rj01), consumo em lote e confirmação de fila vazia após processamento.

5.3. Módulo SNS (self.sns_client & tests/teste_sns.py)
Serviço de mensageria Pub/Sub para disparo imediato de notificações críticas aos administradores/NOC:

Métodos Implementados:

criar_topico_alertas(nome_topico="net-ai-alertas-criticos"): Cria o canal de notificações (create_topic) e retorna o TopicArn.

inscrever_alerta(topic_arn, protocolo, endpoint): Inscreve destinatários (email, https, sqs) no tópico (subscribe).

disparar_alerta_critico(topic_arn, assunto, mensagem): Publica o alerta no tópico (publish) aplicando fatiamento seguro assunto[:100] para respeitar o limite de caracteres do protocolo de e-mail da AWS.

Validação (tests/teste_sns.py): Testada criação do tópico, inscrição de e-mail do NOC e disparo de alerta crítico retornando o MessageId.

6. Próximos Passos
Opção B (Motor de Análise de Rede & IA): Iniciar o desenvolvimento das camadas src/network/drivers.py (aplicando Factory Pattern para coleta/parser de logs de roteadores FRR/MikroTik) e src/ai/analyzer.py (aplicando Strategy Pattern para diagnóstico inteligente via LLM/Ollama) integrando com toda a infraestrutura AWSManager já concluída.


# Contexto do Projeto: Net-AI Remediator
**Data da Última Atualização:** 17 de Novembro de 2026

## 1. Resumo do Progresso de Hoje
Hoje focamos na robustez, segurança e inteligência do motor de IA (`AIAnalyzer`), aplicando conceitos avançados de engenharia de software, Strategy Pattern e RAG (Retrieval-Augmented Generation) com persistência em nuvem simulada.

---

## 2. Componentes Desenvolvidos e Atualizados

### A. Camada de IA & Segurança (`src/ai/analyzer.py`)
* **Modelo Local (Ollama):** Integração com o `llama3` rodando localmente via API (`http://localhost:11434/api/generate`).
* **Respostas Determinísticas:** Configuração de `"temperature": 0.0` no payload do Ollama para eliminar "alucinações" e garantir diagnósticos técnicos consistentes e precisos para engenharia de redes.
* **Blacklist de Segurança de Comandos:** Implementação do método `_validar_comando_seguro` que barra imediatamente comandos destrutivos perigosos (como `reload`, `format`, `erase`, `delete`, `shutdown`, etc.), permitindo que comandos legítimos de diagnóstico com filtros (como `show ip bgp summary | include ...`) passem de forma flexível e segura.
* **RAG (Contexto Histórico):** Injeção dinâmica de incidentes passados recuperados do DynamoDB diretamente no prompt da IA, permitindo correlação avançada de falhas (ex: identificação de flaps intermitentes e falhas recorrentes na mesma interface).

### B. Camada de Simulação de Rede (`src/network/drivers.py` - Iniciado)
* **Strategy Pattern (Clean Architecture):** Criação da interface base abstrata (`NetworkDriverInterface`) padronizando o contrato para coleta de logs e execução de comandos de remediação.
* **Driver Simulado (`SimuladorRoteadorDriver`):** Estrutura inicial criada para simular um roteador de borda (`router-borda-sp01`) gerando logs de queda BGP e simulando a aplicação de remediações na CLI.

---

## 3. Próximos Passos Imediatos
* Finalizar e integrar o fluxo completo do **Simulador de Rede** com o pipeline de ponta a ponta:
  `Simulador de Rede` $\rightarrow$ `Fila SQS` $\rightarrow$ `IA com RAG (Ollama + DynamoDB)` $\rightarrow$ `Armazenamento de Relatório (S3)` $\rightarrow$ `Disparo de Alerta (SNS)`.



  # Contexto do Projeto: Net-AI Remediator
**Data da Última Atualização:** 18 de Novembro de 2026
**Status do Projeto:** Transição para Arquitetura de Produção e Laboratório Avançado (EVE-NG / Dispositivos Reais)

## 1. O Que Já Foi Concluído
* **Camada de IA & Segurança (`src/ai/analyzer.py`):**
  * Integração local com Ollama (`llama3`).
  * Respostas determinísticas estritas (`temperature: 0.0`).
  * Blindagem de comandos (`_validar_comando_seguro`) bloqueando ações destrutivas e permitindo diagnósticos seguros com pipes.
  * RAG (Retrieval-Augmented Generation) com DynamoDB injetando histórico de incidentes passados no prompt.
* **Infraestrutura em Nuvem Local (`LocalStack`):**
  * Configuração e testes validados para S3 (relatórios), DynamoDB (histórico) e SQS/SNS (filas e alertas).
* **Camada de Abstração de Rede (`src/network/drivers.py`):**
  * Criação do padrão *Strategy Pattern* (`NetworkDriverInterface`) e do `SimuladorRoteadorDriver` para testes rápidos sem dependência de hardware pesado.

---

## 2. O Que Iremos Construir (Roadmap Avançado de Engenharia)
* **[Pilar 1] Protocolo de Acesso Real (Netmiko):** Implementação do driver SSH corporativo para interagir com topologias reais ou VMs (EVE-NG/GNS3).
* **[Pilar 2] Resiliência e Tratamento de Erros:** Mecanismos de *retry*, timeout e blindagem contra falhas de conexão de rede.
* **[Pilar 3] Parsing Inteligente de CLI (TextFSM):** Conversão de saídas brutas de texto de roteadores em JSON estruturado para consumo otimizado da IA.
* **[Pilar 4] Sistema de Gatilhos de Eventos (Syslog/Webhooks):** Captura automatizada de logs em tempo real para disparar o pipeline de remediação de ponta a ponta.




## Atualização 22/11/2026


# Contexto do Projeto: Net-AI Remediator
**Data da Última Atualização:** 22 de Novembro de 2026
**Status do Projeto:** Pipeline Principal Integrado com LocalStack, Ollama (`llama3`) e Sincronização de Estado no DynamoDB

Configura��o centralizada (src/core/config.py): Implementa��o da AppConfig (@dataclass(frozen=True)) lendo vari�veis de ambiente (LOCALSTACK_HOST, AWS_DEFAULT_REGION, OLLAMA_MODEL, OLLAMA_URL), definindo padr�es para bucket S3, tabela DynamoDB, fila SQS e t�pico SNS, e expondo localstack_endpoint.

Modelos de dom�nio (src/core/models.py): Formaliza��o das estruturas IncidenteRede e DiagnosticoIA com @dataclass.

Padroniza��o de logging (src/cloud/aws_client.py): Remo��o do logging.basicConfig(...) do m�dulo para centralizar a configura��o de logs no ponto de entrada (main.py).

Orquestra��o e sincroniza��o de estado (main.py): Integra��o do fluxo com driver via factory, modelos, NetworkAIAnalyzer e AWSManager (S3, DynamoDB, SQS, SNS), incluindo log quando o SNS n�o dispara fora de severidades ALTA ou CRITICA e atualiza��o do status do incidente no DynamoDB para REMEDIADO quando aplicar_remediacao(...) retorna True.

Ajustes de rede, IA e higiene de Git: Refinamentos em src/ai/analyzer.py e src/network/drivers.py, atualiza��o do .gitignore (ignorando caches, .env e snapshot*.txt) e remo��o de arquivos .pyc rastreados no �ndice.