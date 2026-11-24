import os
import sys
from unittest.mock import MagicMock, patch

# Garante que a raiz do projeto esteja no sys.path ao rodar o arquivo diretamente
RAIZ_PROJETO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if RAIZ_PROJETO not in sys.path:
    sys.path.insert(0, RAIZ_PROJETO)

import main as main_module


def _preparar_mocks(mock_factory, mock_analyzer):
    driver_fake = MagicMock()
    driver_fake.nome_equipamento = "router-borda-sp01"
    driver_fake.coletar_logs_recentes.return_value = "%BGP-5-ADJCHANGE: neighbor 10.255.255.2 Down"
    driver_fake.aplicar_remediacao.return_value = True
    # Garante que hasattr(driver, "coletar_cli_estruturada") seja False no mock
    del driver_fake.coletar_cli_estruturada

    mock_factory.criar_driver.return_value = driver_fake

    analyzer_fake = MagicMock()
    analyzer_fake.analisar_log_rede.return_value = {
        "diagnostico": "Vizinhança BGP caiu.",
        "severidade": "MEDIA",
        "comando_remediacao": "show ip bgp summary",
    }
    mock_analyzer.return_value = analyzer_fake
    return driver_fake


def testar_repasse_netmiko_explicito():
    aws_fake = MagicMock()
    aws_fake.buscar_historico_equipamento.return_value = []

    with (
        patch.object(main_module, "NetworkDriverFactory") as mock_factory,
        patch.object(main_module, "NetworkAIAnalyzer") as mock_analyzer,
        patch.object(main_module, "_instancia_aws_manager", return_value=aws_fake),
    ):
        _preparar_mocks(mock_factory, mock_analyzer)

        incidente = main_module.executar_pipeline(
            tipo_driver="netmiko",
            equipamento_externo="rtr-oob-01",
            ip_equipamento="10.255.255.10",
            device_type="cisco_ios",
            secret_name="segredo-router-01",
            aws_manager=aws_fake,
        )

        assert incidente.status == "REMEDIADO"
        mock_factory.criar_driver.assert_called_once_with(
            "netmiko",
            nome_equipamento="rtr-oob-01",
            ip="10.255.255.10",
            device_type="cisco_ios",
            secret_name="segredo-router-01",
            aws_manager=aws_fake,
        )

    print("OK: repasse explícito de parâmetros Netmiko validado.")


def testar_fallback_router_secret_name_e_gatilho():
    aws_fake = MagicMock()
    aws_fake.buscar_historico_equipamento.return_value = []

    with (
        patch.dict(os.environ, {"ROUTER_SECRET_NAME": "segredo-via-env"}, clear=False),
        patch.object(main_module, "NetworkDriverFactory") as mock_factory,
        patch.object(main_module, "NetworkAIAnalyzer") as mock_analyzer,
        patch.object(main_module, "_instancia_aws_manager", return_value=aws_fake),
    ):
        _preparar_mocks(mock_factory, mock_analyzer)

        evento = {
            "equipamento": "rtr-oob-02",
            "log_bruto": "%LINK-3-UPDOWN: Interface Ethernet0/1, changed state to down",
            "ip": "10.255.255.20",
            "device_type": "cisco_xe",
        }
        main_module._processar_evento_gatilho(evento, tipo_driver="netmiko")

        mock_factory.criar_driver.assert_called_once_with(
            "netmiko",
            nome_equipamento="rtr-oob-02",
            ip="10.255.255.20",
            device_type="cisco_xe",
            secret_name="segredo-via-env",
            aws_manager=aws_fake,
        )

    print("OK: fallback de ROUTER_SECRET_NAME e gatilho validados.")


def testar_modo_simulador_nao_recebe_extras_netmiko():
    aws_fake = MagicMock()
    aws_fake.buscar_historico_equipamento.return_value = []

    with (
        patch.object(main_module, "NetworkDriverFactory") as mock_factory,
        patch.object(main_module, "NetworkAIAnalyzer") as mock_analyzer,
        patch.object(main_module, "_instancia_aws_manager", return_value=aws_fake),
    ):
        _preparar_mocks(mock_factory, mock_analyzer)

        main_module.executar_pipeline(
            tipo_driver="simulador",
            ip_equipamento="10.255.255.99",
            secret_name="nao-deve-ir",
            aws_manager=aws_fake,
        )

        mock_factory.criar_driver.assert_called_once_with(
            "simulador",
            nome_equipamento="router-borda-sp01",
        )

    print("OK: modo simulador preservado sem parâmetros extras do Netmiko.")


if __name__ == "__main__":
    testar_repasse_netmiko_explicito()
    testar_fallback_router_secret_name_e_gatilho()
    testar_modo_simulador_nao_recebe_extras_netmiko()
    print("\nTodos os testes da Tarefa 3 passaram!")