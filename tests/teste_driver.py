from src.network.drivers import SimuladorRoteadorDriver

def testar_driver_simulado():
    print("--- INICIANDO TESTE DO DRIVER DE REDE ---")
    
    # Instancia o driver simulado
    driver = SimuladorRoteadorDriver("router-borda-sp01")
    
    # Testa a coleta de log
    log = driver.coletar_logs_recentes()
    print(f"\n[LOG CAPTURADO]:\n{log}\n")
    
    # Testa a aplicação de remediação segura
    comando_ia = "clear ip bgp 10.255.0.2 soft"
    sucesso = driver.aplicar_remediacao(comando_ia)
    
    assert sucesso == True, "A remediação deveria ter retornado True"
    print("\n--- TESTE DO DRIVER CONCLUÍDO COM SUCESSO! ---")

if __name__ == "__main__":
    testar_driver_simulado()