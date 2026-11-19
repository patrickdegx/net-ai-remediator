import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.cloud.aws_client import AWSManager


def testar_secrets_manager():
    aws = AWSManager()
    nome_cofre = "net-ai/roteadores/mikrotik-borda"

    print("\n--- 1. GUARDANDO CREDENCIAIS NO COFRE ---")
    credenciais_iniciais = {
        "host": "192.168.88.1",
        "usuario": "admin_netai",
        "senha": "SenhaSuperSecreta@2026!",
        "porta_ssh": "22"
    }
    aws.criar_segredo(
        nome_segredo=nome_cofre,
        segredo_dict=credenciais_iniciais,
        descricao="Credenciais de acesso SSH do roteador MikroTik de borda"
    )

    print("\n--- 2. RECUPERANDO CREDENCIAIS DO COFRE ---")
    dados_recuperados = aws.buscar_segredo(nome_cofre)
    if dados_recuperados:
        print(f"Host: {dados_recuperados['host']} | Usuário: {dados_recuperados['usuario']} | Senha: {dados_recuperados['senha']}")

    print("\n--- 3. ROTACIONANDO (ATUALIZANDO) A SENHA ---")
    credenciais_novas = credenciais_iniciais.copy()
    credenciais_novas["senha"] = aws.gerar_senha_forte(24)
    aws.atualizar_segredo(nome_cofre, credenciais_novas)

    dados_novos = aws.buscar_segredo(nome_cofre)
    if dados_novos:
        print(f"Senha atualizada lida do cofre: {dados_novos['senha']}")


if __name__ == "__main__":
    testar_secrets_manager()