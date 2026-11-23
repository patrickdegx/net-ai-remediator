# Net-AI Remediator

Ferramenta autônoma de monitoramento, diagnóstico e remediação de rede e nuvem em Python (POO), voltada para cenários híbridos (On-Premises + Cloud + IA local).

## Arquitetura
* **Camada de Rede / On-Premises (`src/network/`):** Drivers de conexão (`NetworkDriverInterface`, `SimuladorRoteadorDriver`, `NetmikoRouterDriver`, `NetworkDriverFactory`) e *parser* com templates (`NetworkParser`).
* **Camada de IA (`src/ai/`):** Análise de logs e sugestão de comandos com validação de segurança (`NetworkAIAnalyzer`).
* **Camada Cloud (`src/cloud/`):** Integração com serviços AWS simulados via LocalStack (`AWSManager` — S3, DynamoDB, Secrets Manager, SQS e SNS).
* **Core e Modelos (`src/core/`):** Configurações centralizadas (`config.py`) e estruturas de dados (`models.py`).

## Fluxo de Execução
1. Coleta ou simulação de dados/logs de rede via drivers (`src/network/`).
2. Normalização/interpretação das saídas com templates (`parser.py`).
3. Diagnóstico e validação de comandos de remediação via IA (`analyzer.py`).
4. Registro, armazenamento de relatórios e alertas/filas na camada cloud (`aws_client.py`).

## Como Executar
1. Suba os serviços simulados com Docker Compose:
   ```bash
   docker-compose -f infra/docker-compose.yml up -d