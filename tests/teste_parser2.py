import sys
import os

# Garante que o Python encontre a pasta src
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.network.parser import NetworkParser

def testar_parser():
    print("--- INICIANDO TESTE DO PARSER (TEXTFSM COM ARQUIVO) ---")
    
    # Saída bruta simulada do BGP
    raw_output = """
10.255.0.1        4      65000       120       140         0         0         0      0
10.255.0.2        4      65001       250       300         0         0         0     10
    """
    
    # Caminho para o arquivo de template TextFSM
    template_path = os.path.join(os.path.dirname(__file__), '../src/network/templates/bgp_summary.template')
    
    print(f"Lendo template do arquivo: {template_path}")
    resultado = NetworkParser.parsear_arquivo(template_path, raw_output)
    
    print("\n[RESULTADO CONVERTIDO EM JSON/DICIONÁRIO]:")
    if resultado:
        for item in resultado:
            print(item)
    else:
        print("Nenhum registro encontrado. Verifique o template.")
        
    print("\n--- TESTE DO PARSER FINALIZADO COM SUCESSO ---")

if __name__ == "__main__":
    testar_parser()