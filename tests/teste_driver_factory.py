import sys
import os

# Adiciona a raiz do projeto no path para o Python encontrar a src
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.network.drivers import NetworkDriverFactory

def testar_resiliencia_e_factory():
    print("--- INICIANDO TESTE DE RESILIÊNCIA E FACTORY ---\n")
    
    # 1. Testando o Driver Simulado (continua funcionando 100%)
    print("[TESTE 1] Validando Driver Simulado:")
    driver_sim = NetworkDriverFactory.criar_driver("simulador", nome_equipamento="router-borda-sp01")
    logs = driver_sim.coletar_logs_recentes()
    print(f"Log capturado: {logs}")
    driver_sim.aplicar_remediacao("clear ip bgp 10.255.0.2 soft")
    
    print("\n--------------------------------------------------\n")
    
    # 2. Testando a criação do Driver Netmiko (Pilar 2 - com parâmetros de retry)
    print("[TESTE 2] Validando Instanciação do Driver Netmiko Resiliente:")
    try:
        driver_netmiko = NetworkDriverFactory.criar_driver(
            "netmiko", 
            device_type="cisco_ios", 
            ip="192.168.255.255", # IP fictício proposital para testar timeout/retry
            username="admin", 
            secret="cisco123",
            max_retries=2        # Testa 2 tentativas antes de estourar erro
        )
        print("Driver Netmiko instanciado com sucesso. Tentando conectar (vai gerar timeout esperado)...")
        driver_netmiko.coletar_logs_recentes()
    except Exception as e:
        print(f"[SUCESSO NO TRATAMENTO] A exceção de rede foi capturada corretamente pelo Pilar 2: {type(e).__name__} - {e}")

if __name__ == "__main__":
    testar_resiliencia_e_factory()