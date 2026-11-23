import os
import sys

# Garante que a raiz do projeto esteja no sys.path para importar módulos do projeto.
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


def testar_dockerfile():
    # Exibe o cabeçalho de início do teste específico do Dockerfile.
    print("--- TESTE DO DOCKERFILE: CMD APONTANDO PARA MAIN.PY ---")

    # Localiza o Dockerfile na raiz do repositório.
    caminho_dockerfile = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "Dockerfile")
    )
    assert os.path.exists(caminho_dockerfile), f"Arquivo não encontrado: {caminho_dockerfile}"

    # Lê o conteúdo do Dockerfile em UTF-8.
    with open(caminho_dockerfile, "r", encoding="utf-8") as arquivo:
        conteudo = arquivo.read()

    # Confere que o CMD antigo de teste não está mais lá e que o CMD atual roda main.py.
    assert 'CMD ["python", "-m", "tests.teste_driver"]' not in conteudo, (
        "Ainda há o CMD antigo de teste no Dockerfile."
    )
    assert 'CMD ["python", "main.py"]' in conteudo, (
        'Esperava \'CMD ["python", "main.py"]\' no Dockerfile.'
    )

    print('Dockerfile validado: CMD ["python", "main.py"] configurado.')
    print("--- TESTE DO DOCKERFILE CONCLUÍDO COM SUCESSO ---")


if __name__ == "__main__":
    testar_dockerfile()