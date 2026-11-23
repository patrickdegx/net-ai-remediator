import os
import sys
from unittest.mock import MagicMock

# Garante que a raiz do projeto esteja no sys.path para importar main.py e pacotes de src/.
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import main as main_module


def testar_main_com_evento_externo(monkeypatch):
    # Exibe o cabeçalho do teste de integração do gatilho com main.py.
    print("--- TESTE MAIN.PY: INTEGRAÇÃO COM EVENTO EXTERNO ---")

    # Evita chamadas reais ao LocalStack/AWS e ao Ollama durante este teste focado no fluxo do main.py.
    monkeypatch.setattr(main_module, "AWSManager", None)

    fake_analyzer = MagicMock()
    fake_analyzer.analisar_log_rede.return_value = {
        "diagnostico": "Vizinho BGP 10.255.0.2 caiu por hold timer.",
        "severidade": "ALTA",
        "comando_remediacao": "clear ip bgp 10.255.0.2 soft",
    }
    monkeypatch.setattr(main_module, "NetworkAIAnalyzer", lambda **kwargs: fake_analyzer)

    evento_simulado = {
        "equipamento": "router-core-pr01",
        "log_bruto": "%BGP-5-ADJCHANGE: neighbor 10.255.0.2 Down - Hold Timer Expired",
        "origem": "webhook",
    }

    # Dispara o fluxo pelo helper de gatilho do main.py.
    incidente = main_module._processar_evento_gatilho(evento_simulado, tipo_driver="simulador")

    # Confere que o equipamento e o log externo foram usados e o incidente avançou até REMEDIADO.
    assert incidente.equipamento == "router-core-pr01"
    assert incidente.severidade == "ALTA"
    assert incidente.status == "REMEDIADO"
    assert "%BGP-5-ADJCHANGE: neighbor 10.255.0.2 Down" in fake_analyzer.analisar_log_rede.call_args.kwargs["log_bruto"]

    print(f"OK -> Incidente {incidente.incidente_id} processado para {incidente.equipamento} com status {incidente.status}.")
    print("--- TESTE MAIN.PY CONCLUÍDO COM SUCESSO ---")


if __name__ == "__main__":
    import pytest

    raise SystemExit(pytest.main([__file__]))