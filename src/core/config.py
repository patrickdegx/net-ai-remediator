# Biblioteca padrão do Python para ler variáveis de ambiente do sistema operacional
# ou do container (ex.: LOCALSTACK_HOST, AWS_DEFAULT_REGION, OLLAMA_URL).
import os

# Decorador da biblioteca padrão do Python (adicionado no Python 3.7) que gera
# automaticamente métodos úteis em classes focadas em guardar dados (como __init__,
# __repr__ e __eq__), evitando código repetitivo.
from dataclasses import dataclass


# @dataclass(frozen=True) transforma AppConfig em uma classe de dados "imutável":
# depois de criada, tentar alterar um atributo (ex.: cfg.s3_bucket = "outro") gera erro.
# Isso ajuda a evitar que alguma parte do código mude configuração sem querer em execução.
@dataclass(frozen=True)
class AppConfig:
    # os.getenv("NOME_VARIAVEL", "valor_padrao"):
    # Se existir a variável de ambiente (por exemplo, dentro do Docker Compose), usa ela;
    # se não existir, cai no valor padrão seguro ("localhost").
    localstack_host: str = os.getenv("LOCALSTACK_HOST", "localhost")
    aws_region: str = os.getenv("AWS_DEFAULT_REGION", "us-east-1")

    # Nomes padrão dos recursos usados no projeto (LocalStack / AWS).
    # O ": str" após o nome é um "type hint" (dica de tipo) para legibilidade e editores.
    s3_bucket: str = "net-ai-remediator-relatorios"
    dynamodb_table: str = "net-ai-incidentes"
    sqs_queue_name: str = "net-ai-alertas-queue"
    sns_topic_name: str = "net-ai-alertas-criticos"

    # Configurações do modelo local de IA via Ollama.
    ollama_model: str = os.getenv("OLLAMA_MODEL", "llama3")
    ollama_url: str = os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate")

    def __post_init__(self) -> None:
        # Como a dataclass é frozen=True, usamos object.__setattr__ para normalizar
        # a URL uma única vez após a inicialização, evitando duplicar /api/generate.
        url_padrao = "http://localhost:11434/api/generate"
        url_limpa = (self.ollama_url or url_padrao).strip().rstrip("/")
        if not url_limpa.endswith("/api/generate"):
            url_limpa = f"{url_limpa}/api/generate"
        object.__setattr__(self, "ollama_url", url_limpa)

    # @property faz um método se comportar como um atributo somente leitura:
    # você acessa `config.localstack_endpoint` (sem parênteses), e ele monta a URL
    # dinamicamente com base no `localstack_host` atual.
    @property
    def localstack_endpoint(self) -> str:
        # f-string: permite inserir variáveis direto dentro da string usando {chaves}.
        return f"http://{self.localstack_host}:4566"


