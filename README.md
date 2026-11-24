# Net-AI Remediator

Ferramenta em Python de monitoramento, diagnóstico e remediação de incidentes de rede e nuvem, combinando drivers de rede, *parsing* com TextFSM, análise com IA local via Ollama e serviços AWS simulados via LocalStack.

**Última atualização:** 24/11/2026

## Arquitetura e Módulos
- **Camada de Rede (`src/network/`):** `NetworkDriverInterface`, `SimuladorRoteadorDriver`, `NetmikoRouterDriver` (com *retry/backoff* e tratamento de erros), `NetworkDriverFactory`, `NetworkParser` e *templates* em `src/network/templates/`[cite: 4, 5].
- **Camada de IA (`src/ai/`):** `NetworkAIAnalyzer` integrado ao Ollama (`llama3`, `temperature: 0.0`), com suporte a histórico recente (RAG) do DynamoDB, validação de comandos seguros e *fallback*[cite: 2, 5].
- **Camada Cloud (`src/cloud/`):** `AWSManager` operando com LocalStack (`S3`, `DynamoDB`, `Secrets Manager`, `SQS` e `SNS`), incluindo consulta de histórico de incidentes por equipamento (`buscar_historico_equipamento`)[cite: 4, 5].
- **Core (`src/core/`):** `AppConfig` em `config.py` e modelos `IncidenteRede` e `DiagnosticoIA` em `models.py`[cite: 1, 3, 5].
- **Orquestração (`main.py`):** Coordena coleta/simulação, coleta estruturada de CLI via TextFSM, consulta de histórico no DynamoDB, análise via IA, persistência/alertas/filas na camada cloud, remediação e sincronização de estado para `REMEDIADO` no DynamoDB[cite: 3, 6].

## Como Executar

1. **Suba a infraestrutura local (LocalStack / Docker):**
   ```bash
   docker compose -f infra/docker-compose.yml up -d


Instale as dependências:


pip install -r requirements.txt
