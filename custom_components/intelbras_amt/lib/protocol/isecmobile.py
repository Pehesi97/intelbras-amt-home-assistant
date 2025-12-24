"""Frame ISECMobile - Camada de comandos do protocolo.

O frame ISECMobile contém os comandos enviados à central de alarme.
Este frame é encapsulado dentro de um frame ISECNet para transmissão.

Estrutura do frame:
| Campo      | Bytes | Descrição                              |
|------------|-------|----------------------------------------|
| Início     | 1     | 0x21 ("!") - delimitador               |
| Senha      | 4-6   | Senha ASCII do usuário                 |
| Comando    | 1-2   | Código do comando                      |
| Conteúdo   | 0-52  | Dados do comando (opcional)            |
| Fim        | 1     | 0x21 ("!") - delimitador               |

Exemplo da documentação (ativação completa):
    21 31 32 33 34 41 21
    - 21: Início do frame
    - 31 32 33 34: Senha "1234" em ASCII
    - 41: Comando de ativação
    - 21: Fim do frame
"""

from dataclasses import dataclass, field
from typing import Self

from ..const import (
    ISECMOBILE_FRAME_DELIMITER,
    ISECMOBILE_PASSWORD_MIN_LEN,
    ISECMOBILE_PASSWORD_MAX_LEN,
    ISECMOBILE_CONTENT_MAX_LEN,
)


class ISECMobileError(Exception):
    """Erro de parsing ou validação de frame ISECMobile."""
    pass


@dataclass
class ISECMobileFrame:
    """Representa um frame do protocolo ISECMobile.
    
    Attributes:
        password: Senha do usuário (string ou bytes).
        command: Código do comando (1-2 bytes).
        content: Conteúdo/dados do comando (opcional).
    """
    
    password: bytes
    command: bytes
    content: bytes = field(default_factory=bytes)

    @classmethod
    def create(
        cls,
        password: str | bytes,
        command: int | bytes,
        content: bytes | None = None,
    ) -> Self:
        """Cria um frame ISECMobile.
        
        Args:
            password: Senha do usuário (4-6 caracteres/bytes).
            command: Código do comando (int ou bytes).
            content: Dados opcionais do comando.
            
        Returns:
            Instância de ISECMobileFrame.
            
        Raises:
            ISECMobileError: Se os parâmetros forem inválidos.
        """
        # Converte senha para bytes
        if isinstance(password, str):
            password_bytes = password.encode('ascii')
        else:
            password_bytes = bytes(password)
        
        # Valida tamanho da senha
        if not ISECMOBILE_PASSWORD_MIN_LEN <= len(password_bytes) <= ISECMOBILE_PASSWORD_MAX_LEN:
            raise ISECMobileError(
                f"Senha deve ter entre {ISECMOBILE_PASSWORD_MIN_LEN} e "
                f"{ISECMOBILE_PASSWORD_MAX_LEN} caracteres, "
                f"recebido {len(password_bytes)}"
            )
        
        # Converte comando para bytes
        if isinstance(command, int):
            command_bytes = bytes([command])
        else:
            command_bytes = bytes(command)
        
        if not 1 <= len(command_bytes) <= 2:
            raise ISECMobileError(
                f"Comando deve ter 1 ou 2 bytes, recebido {len(command_bytes)}"
            )
        
        # Valida conteúdo
        content_bytes = bytes(content) if content else bytes()
        
        if len(content_bytes) > ISECMOBILE_CONTENT_MAX_LEN:
            raise ISECMobileError(
                f"Conteúdo máximo de {ISECMOBILE_CONTENT_MAX_LEN} bytes, "
                f"recebido {len(content_bytes)}"
            )
        
        return cls(
            password=password_bytes,
            command=command_bytes,
            content=content_bytes,
        )

    def build(self) -> bytes:
        """Constrói o frame completo.
        
        Returns:
            Bytes do frame ISECMobile.
            
        Example:
            >>> frame = ISECMobileFrame.create("1234", 0x41)
            >>> frame.build().hex(' ')
            '21 31 32 33 34 41 21'
        """
        return bytes([
            ISECMOBILE_FRAME_DELIMITER,
            *self.password,
            *self.command,
            *self.content,
            ISECMOBILE_FRAME_DELIMITER,
        ])

    @classmethod
    def parse(cls, data: bytes | bytearray) -> Self:
        """Faz o parsing de bytes em um frame ISECMobile.
        
        Args:
            data: Bytes do frame completo.
            
        Returns:
            Instância de ISECMobileFrame parseada.
            
        Raises:
            ISECMobileError: Se o frame for inválido.
        """
        if len(data) < 6:
            raise ISECMobileError(
                f"Frame muito curto: {len(data)} bytes (mínimo 6)"
            )
        
        # Verifica delimitadores
        if data[0] != ISECMOBILE_FRAME_DELIMITER:
            raise ISECMobileError(
                f"Delimitador inicial inválido: 0x{data[0]:02X} "
                f"(esperado 0x{ISECMOBILE_FRAME_DELIMITER:02X})"
            )
        
        if data[-1] != ISECMOBILE_FRAME_DELIMITER:
            raise ISECMobileError(
                f"Delimitador final inválido: 0x{data[-1]:02X} "
                f"(esperado 0x{ISECMOBILE_FRAME_DELIMITER:02X})"
            )
        
        # Remove delimitadores
        inner = data[1:-1]
        
        if len(inner) < ISECMOBILE_PASSWORD_MIN_LEN + 1:
            raise ISECMobileError(
                f"Conteúdo interno muito curto: {len(inner)} bytes"
            )
        
        # Tenta determinar o tamanho da senha
        # Assumimos que a senha tem entre 4 e 6 bytes
        # O comando vem depois da senha
        # Precisamos encontrar o fim da senha de forma heurística
        
        # Estratégia: Assumir senha de 4 bytes por padrão (mais comum)
        # Se necessário, podemos ajustar baseado no contexto
        password_len = ISECMOBILE_PASSWORD_MIN_LEN
        
        # Verifica se há mais conteúdo para senha maior
        # A senha geralmente é numérica ASCII (0x30-0x39)
        for i in range(ISECMOBILE_PASSWORD_MIN_LEN, min(ISECMOBILE_PASSWORD_MAX_LEN + 1, len(inner) - 1)):
            if inner[i] >= 0x41 and inner[i] <= 0x50:  # Comandos começam geralmente em 0x41+
                password_len = i
                break
        
        password = bytes(inner[:password_len])
        
        # Determina tamanho do comando (1 ou 2 bytes)
        # Comandos conhecidos são de 1 byte, mas o protocolo suporta 2
        remaining = inner[password_len:]
        
        if len(remaining) == 0:
            raise ISECMobileError("Comando ausente no frame")
        
        # Assumimos comando de 1 byte por padrão
        command = bytes([remaining[0]])
        content = bytes(remaining[1:]) if len(remaining) > 1 else bytes()
        
        return cls(password=password, command=command, content=content)

    @classmethod
    def try_parse(cls, data: bytes | bytearray) -> Self | None:
        """Tenta fazer o parsing de bytes, retornando None em caso de erro.
        
        Args:
            data: Bytes do frame completo.
            
        Returns:
            Instância de ISECMobileFrame ou None se inválido.
        """
        try:
            return cls.parse(data)
        except ISECMobileError:
            return None

    @property
    def command_code(self) -> int:
        """Retorna o código do comando como inteiro."""
        return self.command[0]

    @property
    def password_str(self) -> str:
        """Retorna a senha como string."""
        return self.password.decode('ascii', errors='replace')

    def __repr__(self) -> str:
        return (
            f"ISECMobileFrame(password='{self.password_str}', "
            f"command=0x{self.command.hex()}, "
            f"content={self.content.hex(' ') if self.content else 'none'})"
        )



