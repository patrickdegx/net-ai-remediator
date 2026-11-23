Markdown
# Net-AI Remediator

Ferramenta em Python (POO) de monitoramento, diagnóstico e remediação de incidentes de rede e nuvem, combinando drivers de rede, *parsing* com TextFSM, análise com IA local via Ollama e serviços AWS simulados via LocalStack.

**Última atualização:** 23/11/2026

## Arquitetura e Módulos
- **Camada de Rede (`src/network/`):** `NetworkDriverInterface`, `SimuladorRoteadorDriver`, `NetmikoRouterDriver` (com *retry/backoff* e tratamento de erros), `NetworkDriverFactory`, `NetworkParser` e *templates* em `src/network/templates/`.
- **Camada de IA (`src/ai/`):** `NetworkAIAnalyzer` integrado ao Ollama (`llama3`, `temperature: 0.0`), com suporte a histórico recente (RAG) do DynamoDB, validação de comandos seguros e *fallback*.
- **Camada Cloud (`src/cloud/`):** `AWSManager` operando com LocalStack (`S3`, `DynamoDB`, `Secrets Manager`, `SQS` e `SNS`), incluindo consulta de histórico de incidentes por equipamento (`buscar_historico_equipamento`).
- **Core (`src/core/`):** `AppConfig` em `config.py` e modelos `IncidenteRede` e `DiagnosticoIA` em `models.py`.
- **Orquestração (`main.py`):** Coordena coleta/simulação, consulta de histórico no DynamoDB, análise via IA, persistência/alertas/filas na camada cloud, remediação e sincronização de estado para `REMEDIADO` no DynamoDB.

## Como Executar

1. **Suba a infraestrutura local (LocalStack / Docker):**
   ```bash
   docker-compose -f infra/docker-compose.yml up -d




   Instale as dependências:


pip install -r requirements.txt

Configure variáveis de ambiente (opcional): Você pode definir variáveis como LOCALSTACK_HOST, AWS_DEFAULT_REGION, OLLAMA_MODEL e OLLAMA_URL (via ambiente ou arquivo .env local, ignorado pelo Git).

Execute a aplicação ou os testes:

python main.py
python tests/teste_rag_historico.py




