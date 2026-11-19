import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.ai.analyzer import NetworkAIAnalyzer


def testar_analisador_ia():
    print("\n--- INICIANDO TESTE DO ANALISADOR DE IA ---")
    
    ai = NetworkAIAnalyzer(modelo="llama3")

    # Simulando um log de falha real de roteamento
    log_falha = (
        "%BGP-5-ADJCHANGE: neighbor 10.255.0.2 Down - Hold Timer Expired. "
        "Interface Ethernet0/0 flap detected. Packet loss reached 45%."
    )
    equipamento_alvo = "router-borda-sp01"

    print(f"\n[Log Bruto] {log_falha}")
    resultado = ai.analisar_log_rede(log_bruto=log_falha, equipamento=equipamento_alvo)

    print("\n--- RESULTADO DA ANÁLISE DA IA ---")
    print(f"Diagnóstico: {resultado.get('diagnostico')}")
    print(f"Severidade:  {resultado.get('severidade')}")
    print(f"Remediação:  {resultado.get('comando_remediacao')}")


if __name__ == "__main__":
    testar_ai = testar_analisador_ia()