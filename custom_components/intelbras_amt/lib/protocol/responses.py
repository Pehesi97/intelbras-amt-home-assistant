"""Parser de respostas ISECMobile.

A central de alarme responde aos comandos com frames curtos indicando
sucesso (ACK) ou erro (NACK).

Estrutura da resposta (dentro do ISECNet):
    - ACK: 1 byte = 0xFE (sucesso)
    - NACK: 1 byte = 0xE0-0xEA (código de erro)

Exemplo da documentação:
    Resposta ACK (ativação bem-sucedida):
        02 E9 FE EA
        - 02: 2 bytes no pacote
        - E9: Comando ISECMobile
        - FE: ACK (sucesso)
        - EA: Checksum
"""

from dataclasses import dataclass
from enum import Enum
from typing import Self

from ..const import (
    ResponseCode,
    RESPONSE_MESSAGES,
    is_ack,
    is_nack,
)
from .isecnet import ISECNetFrame, ISECNetError


class ResponseType(Enum):
    """Tipo de resposta recebida."""
    
    ACK = "ack"
    """Comando executado com sucesso."""
    
    NACK = "nack"
    """Erro na execução do comando."""
    
    DATA = "data"
    """Resposta com dados (para comandos de consulta)."""
    
    UNKNOWN = "unknown"
    """Resposta desconhecida."""


@dataclass
class Response:
    """Representa uma resposta da central de alarme.
    
    Attributes:
        response_type: Tipo da resposta (ACK, NACK, DATA, UNKNOWN).
        code: Código de resposta (0xFE para ACK, 0xE0-0xEA para NACK).
        data: Dados adicionais da resposta (para respostas tipo DATA).
        raw_frame: Frame ISECNet original.
    """
    
    response_type: ResponseType
    code: int
    data: bytes
    raw_frame: ISECNetFrame

    @property
    def is_success(self) -> bool:
        """Verifica se a resposta indica sucesso."""
        # Respostas com dados grandes (status) são consideradas sucesso
        return self.response_type == ResponseType.ACK or (
            self.response_type == ResponseType.DATA and len(self.data) >= 43
        )

    @property
    def is_error(self) -> bool:
        """Verifica se a resposta indica erro."""
        return self.response_type == ResponseType.NACK

    @property
    def message(self) -> str:
        """Retorna a mensagem descritiva da resposta."""
        if self.response_type == ResponseType.DATA and len(self.data) >= 43:
            return f"Resposta com dados ({len(self.data)} bytes)"
        return RESPONSE_MESSAGES.get(
            self.code, 
            f"Código desconhecido: 0x{self.code:02X}"
        )

    @property
    def error_code(self) -> ResponseCode | None:
        """Retorna o código de erro como enum, se for NACK."""
        if self.is_error:
            try:
                return ResponseCode(self.code)
            except ValueError:
                return None
        return None

    @classmethod
    def from_isecnet_frame(cls, frame: ISECNetFrame) -> Self:
        """Cria uma Response a partir de um frame ISECNet.
        
        Args:
            frame: Frame ISECNet recebido.
            
        Returns:
            Instância de Response parseada.
        """
        content = frame.content
        
        if len(content) == 0:
            return cls(
                response_type=ResponseType.UNKNOWN,
                code=0,
                data=bytes(),
                raw_frame=frame,
            )
        
        # Se o conteúdo tem muitos bytes (43+ para status parcial, 54+ para completo),
        # é uma resposta DATA mesmo que o primeiro byte não seja ACK/NACK
        if len(content) >= 43:
            # Resposta com dados grandes (comandos 0x5A ou 0x5B)
            response_type = ResponseType.DATA
            code = 0x00  # Código neutro para respostas com dados
            data = content  # Todo o conteúdo são os dados
        else:
            code = content[0] if len(content) > 0 else 0
            data = content[1:] if len(content) > 1 else bytes()
            
            # Determina o tipo de resposta
            if is_ack(code):
                response_type = ResponseType.ACK
            elif is_nack(code):
                response_type = ResponseType.NACK
            elif len(data) > 0:
                response_type = ResponseType.DATA
            else:
                response_type = ResponseType.UNKNOWN
        
        return cls(
            response_type=response_type,
            code=code,
            data=data,
            raw_frame=frame,
        )

    @classmethod
    def parse(cls, raw_data: bytes | bytearray) -> Self:
        """Faz o parsing de bytes brutos em uma Response.
        
        Args:
            raw_data: Bytes do pacote ISECNet completo.
            
        Returns:
            Instância de Response parseada.
            
        Raises:
            ISECNetError: Se o frame for inválido.
        """
        frame = ISECNetFrame.parse(raw_data)
        return cls.from_isecnet_frame(frame)

    @classmethod
    def try_parse(cls, raw_data: bytes | bytearray) -> Self | None:
        """Tenta fazer o parsing, retornando None em caso de erro.
        
        Args:
            raw_data: Bytes do pacote ISECNet completo.
            
        Returns:
            Instância de Response ou None se inválido.
        """
        try:
            return cls.parse(raw_data)
        except (ISECNetError, Exception):
            return None

    def __repr__(self) -> str:
        return (
            f"Response(type={self.response_type.value}, "
            f"code=0x{self.code:02X}, "
            f"message='{self.message}')"
        )


class ResponseParser:
    """Parser de respostas com suporte a múltiplos frames.
    
    Útil para processar respostas que podem conter dados adicionais
    ou múltiplos frames.
    """

    @staticmethod
    def parse_ack_response(frame: ISECNetFrame) -> Response:
        """Processa um frame esperando ACK/NACK simples.
        
        Args:
            frame: Frame ISECNet recebido.
            
        Returns:
            Response parseada.
        """
        return Response.from_isecnet_frame(frame)

    @staticmethod
    def is_ack_frame(frame: ISECNetFrame) -> bool:
        """Verifica se um frame é resposta ACK.
        
        Args:
            frame: Frame ISECNet a verificar.
            
        Returns:
            True se for ACK.
        """
        if len(frame.content) == 0:
            return False
        return is_ack(frame.content[0])

    @staticmethod
    def is_nack_frame(frame: ISECNetFrame) -> bool:
        """Verifica se um frame é resposta NACK.
        
        Args:
            frame: Frame ISECNet a verificar.
            
        Returns:
            True se for NACK.
        """
        if len(frame.content) == 0:
            return False
        return is_nack(frame.content[0])

    @staticmethod
    def get_nack_reason(frame: ISECNetFrame) -> str:
        """Obtém a razão de um NACK.
        
        Args:
            frame: Frame ISECNet NACK.
            
        Returns:
            Mensagem descritiva do erro.
        """
        if len(frame.content) == 0:
            return "Resposta vazia"
        code = frame.content[0]
        return RESPONSE_MESSAGES.get(code, f"Erro desconhecido: 0x{code:02X}")

