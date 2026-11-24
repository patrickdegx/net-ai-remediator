import os
import sys

# Garante que a raiz do projeto esteja no sys.path ao rodar o arquivo diretamente
RAIZ_PROJETO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if RAIZ_PROJETO not in sys.path:
    sys.path.insert(0, RAIZ_PROJETO)

from src.core.config import AppConfig


def testar_normalizacao_ollama_url() -> None:
    cfg_sem_path = AppConfig(ollama_url="http://host.docker.internal:11434")
    assert cfg_sem_path.ollama_url == "http://host.docker.internal:11434/api/generate"

    cfg_com_barra = AppConfig(ollama_url="http://host.docker.internal:11434/")
    assert cfg_com_barra.ollama_url == "http://host.docker.internal:11434/api/generate"

    cfg_ja_completo = AppConfig(ollama_url="http://localhost:11434/api/generate")
    assert cfg_ja_completo.ollama_url == "http://localhost:11434/api/generate"

    print("OK: normalizacao de ollama_url validada.")


if __name__ == "__main__":
    testar_normalizacao_ollama_url()