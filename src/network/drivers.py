# Módulos padrão do Python: ipaddress para validar redes de gerência, logging para registros,
# time para backoff em tentativas e abc para definir a interface base do driver.
import ipaddress
import logging
import os
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

# Importa o parser TextFSM responsável por estruturar saídas de CLI em dicionários.
from src.network.parser import NetworkParser

# Tenta importar o Netmiko; se não estiver instalado no ambiente, evita quebrar o simulador.
try:
    from netmiko import ConnectHandler, NetmikoAuthenticationException, NetmikoTimeoutException
    NETMIKO_DISPONIVEL = True
except ImportError:
    NETMIKO_DISPONIVEL = False

# Logger dedicado aos drivers de rede.
logger = logging.getLogger("NetworkDriver")


class NetworkDriverInterface(ABC):
    # Contrato base (Strategy Pattern) para drivers simulados ou reais.
    @abstractmethod
    def coletar_logs_recentes(self) -> str:
        pass

    # Contrato base para aplicar comandos de remediação no equipamento.
    @abstractmethod
    def aplicar_remediacao(self, comando: str) -> bool:
        pass


class SimuladorRoteadorDriver(NetworkDriverInterface):
    # Inicializa o simulador com o nome lógico do equipamento de rede.
    def __init__(self, nome_equipamento: str):
        self.nome_equipamento = nome_equipamento
        logger.info(f"Driver simulado inicializado: {self.nome_equipamento}")

    # Simula a coleta de um log bruto de evento BGP.
    def coletar_logs_recentes(self) -> str:
        return "%BGP-5-ADJCHANGE: neighbor 10.255.0.2 Down - Hold Timer Expired. Interface Ethernet0/0 flap detected."

    # Simula uma saída de CLI BGP e parseia via TextFSM usando o template padrão.
    def coletar_cli_estruturada(
        self,
        comando: str = "show ip bgp summary",
        template_path: str = "src/network/templates/cisco_ios_show_ip_bgp_summary.template",
        raw_cli_output: Optional[str] = None,
    ) -> Dict[str, Any]:
        # Se não for passada saída bruta customizada, usa um exemplo alinhado ao template BGP.
        if raw_cli_output is None:
            raw_cli_output = (
                "10.255.0.1        4      65000       120       140         0         0         0      12\n"
                "10.255.0.2        4      65001       250       300         0         0         0      Idle\n"
            )

        logger.info(f"[{self.nome_equipamento}] Coletando saída de CLI simulada: '{comando}'")

        # Inicia a lista de registros estruturados vazia como fallback seguro.
        dados_estruturados: List[Dict[str, Any]] = []
        # Verifica se o arquivo de template existe no disco antes de chamar o NetworkParser.
        if os.path.exists(template_path):
            dados_estruturados = NetworkParser.parsear_arquivo(template_path, raw_cli_output)
        else:
            logger.warning(
                f"[{self.nome_equipamento}] Template TextFSM não encontrado em '{template_path}'."
            )

        # Retorna saída bruta, comando, equipamento e dados estruturados extraídos pelo TextFSM.
        return {
            "equipamento": self.nome_equipamento,
            "comando": comando,
            "raw_output": raw_cli_output.strip(),
            "parsed_data": dados_estruturados,
        }

    # Simula a execução do comando de remediação na CLI do roteador.
    def aplicar_remediacao(self, comando: str) -> bool:
        print(f"--> [SIMULADOR CLI {self.nome_equipamento}] Comando aplicado com sucesso: {comando}")
        return True


class NetmikoRouterDriver(NetworkDriverInterface):
    """
    Driver de Produção/Laboratório real com resiliência, retry, isolamento de rede
    de gerência e busca de credenciais via AWS Secrets Manager.
    """

    def __init__(
        self,
        device_type: str,
        ip: str,
        username: Optional[str] = None,
        secret: Optional[str] = None,
        port: int = 22,
        max_retries: int = 3,
        retry_delay: int = 2,
        secret_name: Optional[str] = None,
        aws_manager=None,
        rede_gerencia_cidr: Optional[str] = "10.255.255.0/24",
    ):
        # Garante que a biblioteca netmiko esteja disponível antes de configurar conexão SSH.
        if not NETMIKO_DISPONIVEL:
            raise ImportError("A biblioteca 'netmiko' não está instalada. Execute: pip install netmiko")

        # 1. Valida isolamento de rede (rede de gerência dedicada / OOB) quando informado.
        if rede_gerencia_cidr:
            try:
                ip_obj = ipaddress.ip_address(ip)
                rede_obj = ipaddress.ip_network(rede_gerencia_cidr, strict=False)
            except ValueError as exc:
                raise ValueError(
                    f"IP de destino ('{ip}') ou CIDR de gerência ('{rede_gerencia_cidr}') inválido."
                ) from exc

            if ip_obj not in rede_obj:
                raise ValueError(
                    f"Bloqueio de segurança: IP {ip} fora da rede de gerência dedicada ({rede_gerencia_cidr})."
                )

        # 2. Obtém credenciais do AWS Secrets Manager (quando secret_name e aws_manager forem fornecidos)
        # ou usa os parâmetros explícitos (username/secret) mantendo compatibilidade.
        usuario_final = username
        senha_final = secret
        enable_secret_final = secret

        if secret_name and aws_manager is not None:
            credenciais = aws_manager.buscar_segredo(secret_name)
            if not credenciais:
                raise RuntimeError(f"Credenciais '{secret_name}' não encontradas no Secrets Manager.")
            usuario_final = credenciais.get("username") or usuario_final
            senha_final = credenciais.get("password") or senha_final
            enable_secret_final = credenciais.get("enable_secret") or senha_final

        if not usuario_final or not senha_final:
            raise ValueError(
                "Credenciais SSH não informadas. Forneça 'username' e 'secret' ou 'secret_name' + 'aws_manager'."
            )

        # Nota de privilégio mínimo: o usuário SSH configurado no roteador deve possuir
        # apenas o nível de privilégio necessário para os comandos de diagnóstico/remediação.
        self.device_config = {
            "device_type": device_type,
            "host": ip,
            "username": usuario_final,
            "password": senha_final,
            "secret": enable_secret_final,
            "port": port,
            "timeout": 10,
            "session_timeout": 15,
        }
        self.ip = ip
        self.rede_gerencia_cidr = rede_gerencia_cidr
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        logger.info(
            f"Driver Netmiko resiliente configurado para o host: {self.ip} "
            f"(gerência: {self.rede_gerencia_cidr or 'sem restrição CIDR'}, Max retries: {max_retries})"
        )

    # Executa uma função com novas tentativas e backoff exponencial em caso de falha transitória.
    def _executar_com_retry(self, func, *args, **kwargs):
        """Executa uma operação com novas tentativas e intervalo crescente (backoff)."""
        tentativa = 0
        delay_atual = self.retry_delay
        while tentativa < self.max_retries:
            tentativa += 1
            try:
                return func(*args, **kwargs)
            except NetmikoTimeoutException as e:
                logger.warning(
                    f"[TENTATIVA {tentativa}/{self.max_retries}] Timeout em {self.ip}. "
                    f"Tentando novamente em {delay_atual}s..."
                )
                if tentativa == self.max_retries:
                    logger.error(
                        f"[FALHA CRÍTICA] Esgotadas {self.max_retries} tentativas em {self.ip}."
                    )
                    raise ConnectionError(f"Timeout persistente com o roteador {self.ip}") from e
                time.sleep(delay_atual)
                delay_atual *= 2
            except NetmikoAuthenticationException:
                logger.error(
                    f"[ERRO DE SEGURANÇA] Falha de autenticação SSH em {self.ip}. "
                    "Tentativas canceladas."
                )
                raise PermissionError(f"Falha de autenticação no roteador {self.ip}")
            except Exception as e:
                logger.error(
                    f"[ERRO INESPERADO] Falha na tentativa {tentativa} com {self.ip}: {str(e)}"
                )
                if tentativa == self.max_retries:
                    raise
                time.sleep(delay_atual)
                delay_atual *= 2

    # Coleta via SSH o sumário BGP do equipamento real utilizando a política de retry.
    def coletar_logs_recentes(self) -> str:
        def _acao():
            with ConnectHandler(**self.device_config) as conn:
                return conn.send_command("show ip bgp summary")

        logger.info(f"Iniciando coleta com política de resiliência em {self.ip}...")
        return self._executar_com_retry(_acao)

    # Aplica o comando de remediação no equipamento real via SSH utilizando a política de retry.
    def aplicar_remediacao(self, comando: str) -> bool:
        def _acao():
            with ConnectHandler(**self.device_config) as conn:
                # Chama enable() apenas se houver enable_secret configurado; se o usuário já
                # entrar direto com privilégio mínimo suficiente no EXEC, evita falha desnecessária.
                if self.device_config.get("secret"):
                    try:
                        conn.enable()
                    except Exception:
                        logger.debug(
                            f"[{self.ip}] conn.enable() não necessário ou não aplicável ao nível de privilégio atual."
                        )
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
    # Fábrica que instancia o driver adequado conforme o tipo solicitado ("simulador" ou "netmiko").
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
                max_retries=kwargs.get("max_retries", 3),
                retry_delay=kwargs.get("retry_delay", 2),
                secret_name=kwargs.get("secret_name"),
                aws_manager=kwargs.get("aws_manager"),
                rede_gerencia_cidr=kwargs.get("rede_gerencia_cidr", "10.255.255.0/24"),
            )
        else:
            raise ValueError(f"Tipo de driver desconhecido: '{tipo}'.")