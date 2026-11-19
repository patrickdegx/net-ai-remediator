import time
import logging
from abc import ABC, abstractmethod
from typing import Optional

try:
    from netmiko import ConnectHandler, NetmikoTimeoutException, NetmikoAuthenticationException
    NETMIKO_DISPONIVEL = True
except ImportError:
    NETMIKO_DISPONIVEL = False

logger = logging.getLogger("NetworkDriver")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s - %(message)s")


class NetworkDriverInterface(ABC):
    @abstractmethod
    def coletar_logs_recentes(self) -> str:
        pass

    @abstractmethod
    def aplicar_remediacao(self, comando: str) -> bool:
        pass


class SimuladorRoteadorDriver(NetworkDriverInterface):
    def __init__(self, nome_equipamento: str):
        self.nome_equipamento = nome_equipamento
        logger.info(f"Driver simulado inicializado: {self.nome_equipamento}")

    def coletar_logs_recentes(self) -> str:
        return "%BGP-5-ADJCHANGE: neighbor 10.255.0.2 Down - Hold Timer Expired. Interface Ethernet0/0 flap detected."

    def aplicar_remediacao(self, comando: str) -> bool:
        print(f"--> [SIMULADOR CLI {self.nome_equipamento}] Comando aplicado com sucesso: {comando}")
        return True


class NetmikoRouterDriver(NetworkDriverInterface):
    """
    Driver de Produção/Laboratório real com resiliência, retry e tratamento avançado de erros (Pilar 1 e 2).
    """

    def __init__(self, device_type: str, ip: str, username: str, secret: str, port: int = 22, max_retries: int = 3, retry_delay: int = 2):
        if not NETMIKO_DISPONIVEL:
            raise ImportError("A biblioteca 'netmiko' não está instalada. Execute: pip install netmiko")
        
        self.device_config = {
            'device_type': device_type,
            'host': ip,
            'username': username,
            'password': secret,
            'secret': secret,
            'port': port,
            'timeout': 10,
            'session_timeout': 15
        }
        self.ip = ip
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        logger.info(f"Driver Netmiko resiliente configurado para o host: {self.ip} (Max retries: {max_retries})")

    def _executar_com_retry(self, func, *args, **kwargs):
        """
        Método utilitário para aplicar lógica de retry com intervalo progressivo (backoff).
        """
        tentativa = 0
        while tentativa < self.max_retries:
            tentativa += 1
            try:
                return func(*args, **kwargs)
            except NetmikoTimeoutException as e:
                logger.warning(f"[TENTATIVA {tentativa}/{self.max_retries}] Timeout ao conectar em {self.ip}. Tentando novamente em {self.retry_delay}s...")
                if tentativa == self.max_retries:
                    logger.error(f"[FALHA CRÍTICA] Esgotadas todas as {self.max_retries} tentativas de conexão com {self.ip} devido a Timeout.")
                    raise ConnectionError(f"Timeout persistente com o roteador {self.ip}") from e
                time.sleep(self.retry_delay)
                self.retry_delay *= 2  # Backoff exponencial simples
            except NetmikoAuthenticationException:
                logger.error(f"[ERRO DE SEGURANÇA] Falha de autenticação SSH em {self.ip}. Tentativas canceladas.")
                raise PermissionError(f"Falha de autenticação no roteador {self.ip}")
            except Exception as e:
                logger.error(f"[ERRO INESPERADO] Falha na tentativa {tentativa} com {self.ip}: {str(e)}")
                if tentativa == self.max_retries:
                    raise
                time.sleep(self.retry_delay)

    def coletar_logs_recentes(self) -> str:
        def _acao():
            with ConnectHandler(**self.device_config) as conn:
                return conn.send_command("show ip bgp summary")
        
        logger.info(f"Iniciando coleta com política de resiliência em {self.ip}...")
        return self._executar_com_retry(_acao)

    def aplicar_remediacao(self, comando: str) -> bool:
        def _acao():
            with ConnectHandler(**self.device_config) as conn:
                conn.enable()
                output = conn.send_config_set([comando]) if "config" in comando.lower() else conn.send_command(comando)
                logger.info(f"Comando aplicado com sucesso em {self.ip}. Saída:\n{output}")
                return True

        logger.info(f"Iniciando remediação com política de resiliência em {self.ip}: '{comando}'")
        try:
            return self._executar_com_retry(_acao)
        except Exception as e:
            logger.error(f"[FALHA NA REMEDIAÇÃO] Não foi possível aplicar o comando em {self.ip}: {str(e)}")
            return False


class NetworkDriverFactory:
    @staticmethod
    def criar_driver(tipo: str, **kwargs) -> NetworkDriverInterface:
        tipo_normalizado = tipo.lower()
        if tipo_normalizado == "simulador":
            return SimuladorRoteadorDriver(nome_equipamento=kwargs.get("nome_equipamento", "router-borda-sp01"))
        elif tipo_normalizado == "netmiko":
            return NetmikoRouterDriver(
                device_type=kwargs.get("device_type", "cisco_ios"),
                ip=kwargs.get("ip"),
                username=kwargs.get("username"),
                secret=kwargs.get("secret"),
                port=kwargs.get("port", 22),
                max_retries=kwargs.get("max_retries", 3)
            )
        else:
            raise ValueError(f"Tipo de driver desconhecido: '{tipo}'.")