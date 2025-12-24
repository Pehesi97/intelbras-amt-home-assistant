"""Frame ISECNet - Camada de transporte do protocolo.

O frame ISECNet encapsula os comandos ISECMobile para transmissão via TCP.

Estrutura do frame:
| Campo      | Bytes | Descrição                           |
|------------|-------|-------------------------------------|
| Nº Bytes   | 1     | Tamanho total do pacote             |
| Comando    | 1     | 0xE9 para ISECMobile                |
| Conteúdo   | N     | Frame ISECMobile                    |
| Checksum   | 1     | XOR de todos bytes ^ 0xFF           |

Exemplo da documentação:
    Envio: 08 E9 21 31 32 33 34 41 21 5B
    - 08: 8 bytes no pacote
    - E9: Comando ISECMobile
    - 21 31 32 33 34 41 21: Frame ISECMobile
    - 5B: Checksum
"""

from dataclasses import dataclass
from typing import Self

from ..const import ISECNET_COMMAND_MOBILE, ISECNET_COMMAND_HEARTBEAT, ResponseCode
from .checksum import Checksum


class ISECNetError(Exception):
    """Erro de parsing ou validação de frame ISECNet."""
    pass


@dataclass
class ISECNetFrame:
    """Representa um frame do protocolo ISECNet.
    
    Attributes:
        command: Código do comando (geralmente 0xE9 para ISECMobile).
        content: Conteúdo/payload do frame (frame ISECMobile).
    """
    
    command: int
    content: bytes

    @classmethod
    def create_mobile_frame(cls, isecmobile_content: bytes) -> Self:
        """Cria um frame ISECNet para encapsular conteúdo ISECMobile.
        
        Args:
            isecmobile_content: Bytes do frame ISECMobile.
            
        Returns:
            Instância de ISECNetFrame configurada.
        """
        return cls(command=ISECNET_COMMAND_MOBILE, content=isecmobile_content)

    def build(self) -> bytes:
        """Constrói o frame completo pronto para transmissão.
        
        O frame inclui: tamanho, comando, conteúdo e checksum.
        
        O campo "Nº de Bytes" indica quantos bytes seguem após ele,
        excluindo o checksum (ou seja: comando + conteúdo).
        
        Returns:
            Bytes do frame completo.
            
        Example:
            >>> frame = ISECNetFrame.create_mobile_frame(bytes([0x21, 0x31, 0x32, 0x33, 0x34, 0x41, 0x21]))
            >>> frame.build().hex(' ')
            '08 e9 21 31 32 33 34 41 21 5b'
        """
        # Nº de Bytes = comando (1) + conteúdo (N)
        # Não inclui o próprio byte de tamanho nem o checksum
        size = 1 + len(self.content)  # command + content
        
        # Monta o frame sem checksum
        frame_without_checksum = bytes([size, self.command]) + self.content
        
        # Adiciona checksum
        return Checksum.append(frame_without_checksum)

    @classmethod
    def parse(cls, data: bytes | bytearray) -> Self:
        """Faz o parsing de bytes recebidos em um frame ISECNet.
        
        O campo "Nº de Bytes" indica quantos bytes seguem após ele,
        excluindo o checksum. Tamanho total = 1 (size) + size + 1 (checksum).
        
        Args:
            data: Bytes do frame completo (incluindo checksum).
            
        Returns:
            Instância de ISECNetFrame parseada.
            
        Raises:
            ISECNetError: Se o frame for inválido.
        """
        if len(data) < 3:
            raise ISECNetError(f"Frame muito curto: {len(data)} bytes (mínimo 3)")
        
        size = data[0]
        expected_total = size + 2  # size byte + content indicated by size + checksum
        
        if len(data) != expected_total:
            raise ISECNetError(
                f"Tamanho inconsistente: header indica {size} bytes de conteúdo "
                f"(total esperado {expected_total}), recebido {len(data)} bytes"
            )
        
        # Valida checksum
        if not Checksum.validate_packet(data):
            raise ISECNetError("Checksum inválido")
        
        command = data[1]
        content = bytes(data[2:-1])  # Exclui size, command e checksum
        
        return cls(command=command, content=content)

    @classmethod
    def try_parse(cls, data: bytes | bytearray) -> Self | None:
        """Tenta fazer o parsing de bytes, retornando None em caso de erro.
        
        Args:
            data: Bytes do frame completo.
            
        Returns:
            Instância de ISECNetFrame ou None se inválido.
        """
        try:
            return cls.parse(data)
        except ISECNetError:
            return None

    @property
    def is_mobile_command(self) -> bool:
        """Verifica se é um comando ISECMobile (0xE9)."""
        return self.command == ISECNET_COMMAND_MOBILE

    @property
    def is_heartbeat(self) -> bool:
        """Verifica se é um comando de heartbeat (0xF7)."""
        return self.command == ISECNET_COMMAND_HEARTBEAT

    @classmethod
    def create_heartbeat(cls) -> "ISECNetFrame":
        """Cria um frame de heartbeat (0xF7).
        
        Returns:
            Frame de heartbeat pronto para envio.
        """
        return cls(command=ISECNET_COMMAND_HEARTBEAT, content=bytes())

    @classmethod
    def create_ack_response(cls) -> "ISECNetFrame":
        """Cria uma resposta ACK (0xFE) encapsulada em 0xE9.
        
        Usado para responder a comandos ISECMobile.
        
        Returns:
            Frame de resposta ACK encapsulado.
        """
        return cls(command=ISECNET_COMMAND_MOBILE, content=bytes([ResponseCode.ACK]))

    @classmethod
    def create_simple_ack(cls) -> "ISECNetFrame":
        """Cria uma resposta ACK simples (frame curto).
        
        O ACK (0xFE) é enviado diretamente como comando, sem encapsulamento.
        Usado para responder a comandos como 0x94 e 0xF7.
        
        Returns:
            Frame ACK simples.
        """
        return cls(command=ResponseCode.ACK, content=bytes())

    def __repr__(self) -> str:
        return (
            f"ISECNetFrame(command=0x{self.command:02X}, "
            f"content={self.content.hex(' ')})"
        )


class ISECNetFrameReader:
    """Leitor de frames ISECNet de um stream de bytes.
    
    Útil para processar dados recebidos via socket, onde múltiplos
    frames podem chegar ou frames podem chegar parcialmente.
    """

    def __init__(self) -> None:
        """Inicializa o leitor."""
        self._buffer = bytearray()

    def feed(self, data: bytes | bytearray) -> list[ISECNetFrame]:
        """Alimenta dados ao buffer e retorna frames completos.
        
        Args:
            data: Bytes recebidos.
            
        Returns:
            Lista de frames completos parseados.
        """
        self._buffer.extend(data)
        frames: list[ISECNetFrame] = []
        
        while self._try_extract_frame(frames):
            pass
        
        return frames

    def _try_extract_frame(self, frames: list[ISECNetFrame]) -> bool:
        """Tenta extrair um frame do buffer.
        
        Args:
            frames: Lista onde adicionar frames encontrados.
            
        Returns:
            True se um frame foi extraído, False caso contrário.
        """
        if len(self._buffer) < 1:
            return False
        
        # Verifica se é um heartbeat de 1 byte (0xF7)
        # A central envia apenas o byte F7, sem tamanho nem checksum
        if self._buffer[0] == ISECNET_COMMAND_HEARTBEAT:
            frames.append(ISECNetFrame(command=ISECNET_COMMAND_HEARTBEAT, content=bytes()))
            self._buffer.pop(0)
            return True
        
        # Frame normal precisa de pelo menos 3 bytes
        if len(self._buffer) < 3:
            return False
        
        size = self._buffer[0]
        total_size = size + 2  # size byte + content + checksum
        
        if size < 1:
            # Tamanho inválido (deve ter pelo menos o comando), descarta byte
            self._buffer.pop(0)
            return True
        
        if len(self._buffer) < total_size:
            # Aguarda mais dados
            return False
        
        frame_data = bytes(self._buffer[:total_size])
        frame = ISECNetFrame.try_parse(frame_data)
        
        if frame:
            frames.append(frame)
            del self._buffer[:total_size]
        else:
            # Frame inválido, descarta primeiro byte e tenta novamente
            self._buffer.pop(0)
        
        return True

    def clear(self) -> None:
        """Limpa o buffer interno."""
        self._buffer.clear()

    @property
    def pending_bytes(self) -> int:
        """Retorna o número de bytes pendentes no buffer."""
        return len(self._buffer)

