"""Classe base para comandos ISECMobile.

Esta classe define a interface que todos os comandos devem implementar,
permitindo uma arquitetura extensível para adicionar novos comandos.
"""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..isecmobile import ISECMobileFrame
    from ..isecnet import ISECNetFrame


class Command(ABC):
    """Classe base abstrata para comandos ISECMobile.
    
    Subclasses devem implementar:
        - code: Código do comando
        - build_mobile_frame: Construir o frame ISECMobile
    """

    def __init__(self, password: str) -> None:
        """Inicializa o comando com a senha do usuário.
        
        Args:
            password: Senha do usuário para autenticação (4-6 dígitos).
        """
        self._password = password

    @property
    @abstractmethod
    def code(self) -> int:
        """Código do comando (ex: 0x41 para ativação)."""
        ...

    @property
    def password(self) -> str:
        """Senha do usuário."""
        return self._password

    @abstractmethod
    def build_content(self) -> bytes:
        """Constrói o conteúdo específico do comando.
        
        Returns:
            Bytes do conteúdo do comando (pode ser vazio).
        """
        ...

    def build_mobile_frame(self) -> "ISECMobileFrame":
        """Constrói o frame ISECMobile para este comando.
        
        Returns:
            Instância de ISECMobileFrame.
        """
        from ..isecmobile import ISECMobileFrame
        
        return ISECMobileFrame.create(
            password=self._password,
            command=self.code,
            content=self.build_content(),
        )

    def build_net_frame(self) -> "ISECNetFrame":
        """Constrói o frame ISECNet completo para este comando.
        
        Returns:
            Instância de ISECNetFrame pronta para transmissão.
        """
        from ..isecnet import ISECNetFrame
        
        mobile_frame = self.build_mobile_frame()
        return ISECNetFrame.create_mobile_frame(mobile_frame.build())

    def build(self) -> bytes:
        """Constrói os bytes finais prontos para envio via socket.
        
        Returns:
            Bytes do pacote completo (ISECNet com ISECMobile encapsulado).
        """
        return self.build_net_frame().build()

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(password='****', code=0x{self.code:02X})"



