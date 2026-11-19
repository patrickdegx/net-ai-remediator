import logging
import json
import io
from textfsm import TextFSM

logger = logging.getLogger("NetworkParser")

class NetworkParser:
    """
    Responsável por transformar saídas brutas de CLI de roteadores em estruturas limpas utilizando TextFSM.
    """
    
    @staticmethod
    def parsear_texto(template_str: str, raw_output: str) -> list:
        """
        Recebe o conteúdo de um template TextFSM em string e a saída bruta do comando,
        retornando uma lista de dicionários estruturados.
        """
        try:
            template_file = io.StringIO(template_str)
            fsm = TextFSM(template_file)
            resultado = fsm.ParseText(raw_output)
            
            dados_estruturados = [
                dict(zip(fsm.header, linha)) for linha in resultado
            ]
            logger.info(f"Parsing concluído com sucesso. {len(dados_estruturados)} registros extraídos.")
            return dados_estruturados
        except Exception as e:
            logger.error(f"Erro ao processar o TextFSM: {str(e)}")
            return []

    @staticmethod
    def parsear_arquivo(template_path: str, raw_output: str) -> list:
        """
        Lê um arquivo de template TextFSM do disco e aplica na saída bruta do comando.
        """
        try:
            with open(template_path, "r", encoding="utf-8") as f:
                template_conteudo = f.read()
                
            return NetworkParser.parsear_texto(template_conteudo, raw_output)
        except Exception as e:
            logger.error(f"Erro ao carregar o arquivo de template {template_path}: {str(e)}")
            return []