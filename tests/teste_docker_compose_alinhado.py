import os
import sys

# Garante que a raiz do projeto esteja no sys.path para importar módulos do projeto.
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


def testar_docker_compose():
    # Exibe o cabeçalho de início do teste específico do docker-compose.yml.
    print("--- TESTE DO DOCKER-COMPOSE: ALINHAMENTO AO FLUXO PRINCIPAL ---")

    # Localiza o arquivo docker-compose.yml na pasta infra/.
    caminho_compose = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "infra", "docker-compose.yml")
    )
    assert os.path.exists(caminho_compose), f"Arquivo não encontrado: {caminho_compose}"

    # Lê o conteúdo do docker-compose.yml em UTF-8.
    with open(caminho_compose, "r", encoding="utf-8") as arquivo:
        conteudo = arquivo.read()

    # Confere que o comando antigo de teste saiu e o fluxo principal entrou.
    assert "teste_parser2.py" not in conteudo, "Ainda há referência antiga a teste_parser2.py no docker-compose.yml."
    assert "command: python main.py" in conteudo, "Esperava 'command: python main.py' no serviço net-ai-app."

    # Confere a presença das variáveis de ambiente solicitadas para o fluxo principal.
    assert "APP_ENV=local" in conteudo, "Esperava 'APP_ENV=local' no ambiente do net-ai-app."
    assert "OLLAMA_URL=" in conteudo, "Esperava 'OLLAMA_URL=' no ambiente do net-ai-app."

    print("docker-compose.yml validado: command=python main.py, APP_ENV=local e OLLAMA_URL presentes.")
    print("--- TESTE DO DOCKER-COMPOSE CONCLUÍDO COM SUCESSO ---")


if __name__ == "__main__":
    testar_docker_compose()