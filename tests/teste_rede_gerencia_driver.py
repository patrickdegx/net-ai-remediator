import os
import sys
from unittest.mock import patch

# Garante que a raiz do projeto esteja no sys.path ao rodar o teste direto
RAIZ_PROJETO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if RAIZ_PROJETO not in sys.path:
    sys.path.insert(0, RAIZ_PROJETO)

import src.network.drivers as drivers_mod


def testar_validacao_rede_gerencia():
    # Simula netmiko disponível sem precisar abrir conexão SSH real
    with patch.object(drivers_mod, "NETMIKO_DISPONIVEL", True):
        # 1. IP dentro da rede padrão (10.255.255.0/24) deve funcionar
        drv_ok = drivers_mod.NetmikoRouterDriver(
            device_type="cisco_ios",
            ip="10.255.255.10",
            username="admin",
            secret="senha123",
        )
        assert drv_ok.ip == "10.255.255.10"

        # 2. IP fora da rede padrão deve levantar ValueError de bloqueio
        try:
            drivers_mod.NetmikoRouterDriver(
                device_type="cisco_ios",
                ip="192.168.1.10",
                username="admin",
                secret="senha123",
            )
            assert False, "Esperava bloqueio para IP fora de 10.255.255.0/24"
        except ValueError as err:
            assert "fora da rede de gerência dedicada" in str(err)

        # 3. Passando rede_gerencia_cidr=None deve permitir IP fora da faixa padrão
        drv_sem_trava = drivers_mod.NetmikoRouterDriver(
            device_type="cisco_ios",
            ip="192.168.1.10",
            username="admin",
            secret="senha123",
            rede_gerencia_cidr=None,
        )
        assert drv_sem_trava.ip == "192.168.1.10"

    print("OK: Validação da rede de gerência no NetmikoRouterDriver passou!")


if __name__ == "__main__":
    testar_validacao_rede_gerencia()