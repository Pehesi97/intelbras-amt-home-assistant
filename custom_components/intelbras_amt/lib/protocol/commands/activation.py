"""Comando de Ativação (0x41) - Armar central ou partição.

Este comando ativa/arma a central de alarme ou uma partição específica.

Estrutura do comando:
    - Código: 0x41
    - Conteúdo: 0 ou 1 byte
        - NULL (vazio): Ativa a central completa (todas as partições)
        - 0x41: Ativa partição A
        - 0x42: Ativa partição B
        - 0x43: Ativa partição C
        - 0x44: Ativa partição D
        - 0x50: Ativa no modo Stay

Exemplo da documentação:
    Ativação completa:
        Envio: 08 E9 21 31 32 33 34 41 21 5B
        Resposta: 02 E9 FE EA (ACK)
    
    Ativação partição B com senha 6 dígitos:
        09 E9 21 31 32 33 34 41 42 21 18
"""

from typing import Self

from ...const import CommandCode, PartitionCode
from .base import Command


class ActivationCommand(Command):
    """Comando para ativar/armar a central de alarme.
    
    Attributes:
        partition: Partição a ser ativada (None = todas).
    """

    def __init__(
        self,
        password: str,
        partition: PartitionCode | None = None,
    ) -> None:
        """Inicializa o comando de ativação.
        
        Args:
            password: Senha do usuário (4-6 dígitos).
            partition: Partição específica ou None para ativar todas.
        """
        super().__init__(password)
        self._partition = partition

    @property
    def code(self) -> int:
        """Código do comando de ativação (0x41)."""
        return CommandCode.ACTIVATION

    @property
    def partition(self) -> PartitionCode | None:
        """Partição a ser ativada."""
        return self._partition

    def build_content(self) -> bytes:
        """Constrói o conteúdo do comando.
        
        Returns:
            Bytes vazios para ativar todas as partições,
            ou byte da partição específica.
        """
        if self._partition is None or self._partition == PartitionCode.ALL:
            return bytes()
        return bytes([self._partition])

    @classmethod
    def arm_all(cls, password: str) -> Self:
        """Cria comando para armar todas as partições.
        
        Args:
            password: Senha do usuário.
            
        Returns:
            Instância de ActivationCommand.
        """
        return cls(password, partition=None)

    @classmethod
    def arm_partition_a(cls, password: str) -> Self:
        """Cria comando para armar partição A.
        
        Args:
            password: Senha do usuário.
            
        Returns:
            Instância de ActivationCommand.
        """
        return cls(password, partition=PartitionCode.PARTITION_A)

    @classmethod
    def arm_partition_b(cls, password: str) -> Self:
        """Cria comando para armar partição B.
        
        Args:
            password: Senha do usuário.
            
        Returns:
            Instância de ActivationCommand.
        """
        return cls(password, partition=PartitionCode.PARTITION_B)

    @classmethod
    def arm_partition_c(cls, password: str) -> Self:
        """Cria comando para armar partição C.
        
        Args:
            password: Senha do usuário.
            
        Returns:
            Instância de ActivationCommand.
        """
        return cls(password, partition=PartitionCode.PARTITION_C)

    @classmethod
    def arm_partition_d(cls, password: str) -> Self:
        """Cria comando para armar partição D.
        
        Args:
            password: Senha do usuário.
            
        Returns:
            Instância de ActivationCommand.
        """
        return cls(password, partition=PartitionCode.PARTITION_D)

    @classmethod
    def arm_stay(cls, password: str) -> Self:
        """Cria comando para armar no modo Stay.
        
        Args:
            password: Senha do usuário.
            
        Returns:
            Instância de ActivationCommand.
        """
        return cls(password, partition=PartitionCode.STAY_MODE)

    def __repr__(self) -> str:
        partition_str = self._partition.name if self._partition else "ALL"
        return f"ActivationCommand(password='****', partition={partition_str})"



