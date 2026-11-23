import os
import sys

# Garante que a raiz do projeto esteja no sys.path para importar os pacotes de src/.
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.network.drivers import NetworkDriverFactory


def testar_driver_cli_estruturada():
    # Exibe o cabeçalho de início do teste específico do driver.
    print("--- TESTE DO DRIVER: coletar_cli_estruturada ---")

    # Instancia o driver simulado pela Factory do projeto.
    driver = NetworkDriverFactory.criar_driver("simulador", nome_equipamento="router-borda-sp01")

    # Executa a coleta estruturada usando o template padrão cisco_ios_show_ip_bgp_summary.template.
    resultado = driver.coletar_cli_estruturada()

    # Garante que o dicionário contém a saída bruta e a lista parseada pelo TextFSM.
    assert isinstance(resultado, dict)
    assert resultado.get("equipamento") == "router-borda-sp01"
    assert resultado.get("comando") == "show ip bgp summary"
    assert isinstance(resultado.get("raw_output"), str) and len(resultado["raw_output"]) > 0
    assert isinstance(resultado.get("parsed_data"), list) and len(resultado["parsed_data"]) > 0

    print("\n[SAÍDA BRUTA CLI]:")
    print(resultado["raw_output"])

    print("\n[DADOS ESTRUTURADOS VIA TEXTFSM]:")
    for registro in resultado["parsed_data"]:
        print(registro)

    print("\n--- TESTE DO DRIVER CONCLUÍDO COM SUCESSO ---")


if __name__ == "__main__":
    testar_driver_cli_estruturada()