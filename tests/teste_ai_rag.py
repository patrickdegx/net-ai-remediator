import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.ai.analyzer import NetworkAIAnalyzer


def testar_ai_com_rag():
    print("\n--- INICIANDO TESTE DE IA COM CONTEXTO RAG (HISTÓRICO) ---")
    
    ai = NetworkAIAnalyzer(modelo="llama3")

    # Simulando que o DynamoDB nos devolveu 2 quedas anteriores deste mesmo roteador hoje
    historico_ficticio_dynamodb = [
        {
            "incidente_id": "INC-2026-1117-01",
            "status": "ANALISADO",
            "diagnostico": "Queda anterior de BGP na interface Ethernet0/0 devido a timeout."
        },
        {
            "incidente_id": "INC-2026-1117-02",
            "status": "ANALISADO",
            "diagnostico": "Segundo flap consecutivo na mesma interface Ethernet0/0."
        }
    ]

    log_atual = "%BGP-5-ADJCHANGE: neighbor 10.255.0.2 Down - Hold Timer Expired. 3rd flap in 30 minutes."
    equipamento_alvo = "router-borda-sp01"

    print(f"\n[Equipamento] {equipamento_alvo}")
    print(f"[Log Atual] {log_atual}")
    print(f"[RAG] Fornecendo {len(historico_ficticio_dynamodb)} incidentes anteriores do DynamoDB para a IA...")

    resultado = ai.analisar_log_rede(
        log_bruto=log_atual,
        equipamento=equipamento_alvo,
        historico_recente=historico_ficticio_dynamodb
    )

    print("\n--- RESULTADO DA ANÁLISE COM HISTÓRICO (RAG) ---")
    print(f"Diagnóstico: {resultado.get('diagnostico')}")
    print(f"Severidade:  {resultado.get('severidade')}")
    print(f"Remediação:  {resultado.get('comando_remediacao')}")


if __name__ == "__main__":
    testar_ai_com_rag()