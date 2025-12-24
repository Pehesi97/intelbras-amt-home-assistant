"""Comando 0x94 - Identificação da Central ao Conectar.

A central envia este comando logo após estabelecer a conexão TCP
para informar seu número de conta (Contact-ID) e endereço MAC parcial.

Estrutura do conteúdo (6 bytes):
| Byte | Campo   | Descrição                                    |
|------|---------|----------------------------------------------|
| 1    | Canal   | 0x45='E' (Ethernet), 0x47='G', 0x48='H' GPRS |
| 2    | ID1     | Primeiro byte da conta (2 nibbles)           |
| 3    | ID2     | Segundo byte da conta (2 nibbles)            |
| 4    | MAC1    | Último byte -2 do MAC                        |
| 5    | MAC2    | Último byte -1 do MAC                        |
| 6    | MAC3    | Último byte do MAC                           |

Exemplo:
    45 12 34 30 00 01
    - Canal: Ethernet
    - Conta: 1234
    - MAC: ...30:00:01
"""

from dataclasses import dataclass
from enum import Enum


class ConnectionChannel(Enum):
    """Canal de conexão da central."""
    
    ETHERNET = 0x45  # 'E'
    GPRS_SIM1 = 0x47  # 'G'
    GPRS_SIM2 = 0x48  # 'H'
    
    @classmethod
    def from_byte(cls, value: int) -> "ConnectionChannel":
        """Cria a partir de um byte."""
        for channel in cls:
            if channel.value == value:
                return channel
        raise ValueError(f"Canal desconhecido: 0x{value:02X}")
    
    @property
    def name_pt(self) -> str:
        """Nome em português."""
        names = {
            ConnectionChannel.ETHERNET: "Ethernet",
            ConnectionChannel.GPRS_SIM1: "GPRS SIM 1",
            ConnectionChannel.GPRS_SIM2: "GPRS SIM 2",
        }
        return names.get(self, "Desconhecido")


@dataclass
class ConnectionInfo:
    """Informações de identificação da central.
    
    Parseado do comando 0x94 enviado pela central ao conectar.
    """
    
    channel: ConnectionChannel
    account: str
    mac_suffix: str
    raw_data: bytes
    
    @classmethod
    def parse(cls, data: bytes) -> "ConnectionInfo":
        """Faz o parsing do conteúdo do comando 0x94.
        
        Args:
            data: 6 bytes do conteúdo do comando.
            
        Returns:
            ConnectionInfo parseado.
            
        Raises:
            ValueError: Se os dados forem inválidos.
        """
        if len(data) != 6:
            raise ValueError(f"Comando 0x94 deve ter 6 bytes, recebido {len(data)}")
        
        # Byte 0: Canal
        try:
            channel = ConnectionChannel.from_byte(data[0])
        except ValueError:
            # Canal desconhecido, assume Ethernet
            channel = ConnectionChannel.ETHERNET
        
        # Bytes 1-2: Conta (cada nibble é um dígito)
        # ID1 = data[1], ID2 = data[2]
        # Cada byte tem 2 nibbles (0-F), formando 4 dígitos
        id1 = data[1]
        id2 = data[2]
        
        # Extrai os 4 dígitos da conta
        digit1 = (id1 >> 4) & 0x0F
        digit2 = id1 & 0x0F
        digit3 = (id2 >> 4) & 0x0F
        digit4 = id2 & 0x0F
        
        account = f"{digit1:X}{digit2:X}{digit3:X}{digit4:X}"
        
        # Bytes 3-5: MAC (últimos 3 bytes)
        mac_suffix = f"{data[3]:02X}:{data[4]:02X}:{data[5]:02X}"
        
        return cls(
            channel=channel,
            account=account,
            mac_suffix=mac_suffix,
            raw_data=bytes(data),
        )
    
    @classmethod
    def try_parse(cls, data: bytes) -> "ConnectionInfo | None":
        """Tenta fazer o parsing, retorna None se falhar."""
        try:
            return cls.parse(data)
        except (ValueError, IndexError):
            return None
    
    def __repr__(self) -> str:
        return (
            f"ConnectionInfo(channel={self.channel.name_pt}, "
            f"account='{self.account}', mac=...{self.mac_suffix})"
        )


# Código do comando
CONNECTION_INFO_COMMAND = 0x94



