import os
import sys

# Garante que a raiz do projeto esteja no sys.path ao executar o script diretamente
RAIZ_PROJETO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if RAIZ_PROJETO not in sys.path:
    sys.path.insert(0, RAIZ_PROJETO)

from src.network.drivers import SimuladorRoteadorDriver
from src.network.parser import NetworkParser

PASTA_TEMPLATES = os.path.join(RAIZ_PROJETO, "src", "network", "templates")
TEMPLATE_BGP_SUMMARY = os.path.join(PASTA_TEMPLATES, "bgp_summary.template")
TEMPLATE_CISCO_IOS = os.path.join(PASTA_TEMPLATES, "cisco_ios_show_ip_bgp_summary.template")

# Saída de exemplo com vizinho estabelecido (prefixos numéricos) e vizinho caído em estado "Idle"
SAIDA_LAB_BGP = (
    "10.255.0.1        4      65000       120       140         0         0         0      12\n"
    "10.255.0.2        4      65001       250       300         0         0         0      Idle\n"
)


def testar_templates_bgp():
    assert os.path.exists(TEMPLATE_BGP_SUMMARY), f"Arquivo não encontrado: {TEMPLATE_BGP_SUMMARY}"
    assert os.path.exists(TEMPLATE_CISCO_IOS), f"Arquivo não encontrado: {TEMPLATE_CISCO_IOS}"

    # 1. Testa parsear direto usando bgp_summary.template
    dados_bgp_summary = NetworkParser.parsear_arquivo(TEMPLATE_BGP_SUMMARY, SAIDA_LAB_BGP)
    print(f"[bgp_summary.template] Registros extraídos: {len(dados_bgp_summary)} -> {dados_bgp_summary}")

    # 2. Testa parsear direto usando cisco_ios_show_ip_bgp_summary.template
    dados_cisco_ios = NetworkParser.parsear_arquivo(TEMPLATE_CISCO_IOS, SAIDA_LAB_BGP)
    print(f"[cisco_ios_show_ip_bgp_summary.template] Registros extraídos: {len(dados_cisco_ios)} -> {dados_cisco_ios}")

    # 3. Testa o SimuladorRoteadorDriver usando o template padrão configurado nele
    driver = SimuladorRoteadorDriver("router-borda-sp01")
    resultado_padrao = driver.coletar_cli_estruturada(raw_cli_output=SAIDA_LAB_BGP)
    print(f"[Simulador padrão] Registros extraídos: {len(resultado_padrao['parsed_data'])}")

    # 4. Testa o SimuladorRoteadorDriver apontando explicitamente para bgp_summary.template
    resultado_bgp = driver.coletar_cli_estruturada(
        template_path=TEMPLATE_BGP_SUMMARY,
        raw_cli_output=SAIDA_LAB_BGP,
    )
    print(f"[Simulador com bgp_summary.template] Registros extraídos: {len(resultado_bgp['parsed_data'])}")

    # O template cisco_ios_show_ip_bgp_summary.template deve extrair os 2 vizinhos (incluindo "Idle")
    assert len(dados_cisco_ios) == 2, "Esperava 2 vizinhos extraídos no template Cisco IOS"
    assert dados_cisco_ios[1]["STATE_PFXRCV"] == "Idle"


if __name__ == "__main__":
    testar_templates_bgp()
    print("\nTeste de templates BGP concluído!")