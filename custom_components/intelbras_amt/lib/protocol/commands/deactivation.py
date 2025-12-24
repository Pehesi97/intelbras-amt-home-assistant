"""Comando de Desativação (0x44) - Desarmar central ou partição.

Este comando desativa/desarma a central de alarme ou uma partição específica.

Estrutura do comando:
    - Código: 0x44
    - Conteúdo: 0 ou 1 byte
        - NULL (vazio): Desativa a central completa (todas as partições)
        - 0x41: Desativa partição A
        - 0x42: Desativa partição B
        - 0x43: Desativa partição C
        - 0x44: Desativa partição D

Exemplos da documentação:
    Desativação completa com senha 4 dígitos:
        Envio: 08 E9 21 31 32 33 34 44 21 5E
        Resposta: 02 E9 FE EA (ACK)
    
    Desativação partição A com senha 4 dígitos (1234):
        09 E9 21 31 32 33 34 44 41 21 1E
"""

from typing import Self

from ...const import CommandCode, PartitionCode
from .base import Command


class DeactivationCommand(Command):
    """Comando para desativar/desarmar a central de alarme.
    
    Attributes:
        partition: Partição a ser desativada (None = todas).
    """

    def __init__(
        self,
        password: str,
        partition: PartitionCode | None = None,
    ) -> None:
        """Inicializa o comando de desativação.
        
        Args:
            password: Senha do usuário (4-6 dígitos).
            partition: Partição específica ou None para desativar todas.
        """
        super().__init__(password)
        self._partition = partition

    @property
    def code(self) -> int:
        """Código do comando de desativação (0x44)."""
        return CommandCode.DEACTIVATION

    @property
    def partition(self) -> PartitionCode | None:
        """Partição a ser desativada."""
        return self._partition

    def build_content(self) -> bytes:
        """Constrói o conteúdo do comando.
        
        Returns:
            Bytes vazios para desativar todas as partições,
            ou byte da partição específica.
        """
        if self._partition is None or self._partition == PartitionCode.ALL:
            return bytes()
        return bytes([self._partition])

    @classmethod
    def disarm_all(cls, password: str) -> Self:
        """Cria comando para desarmar todas as partições.
        
        Args:
            password: Senha do usuário.
            
        Returns:
            Instância de DeactivationCommand.
        """
        return cls(password, partition=None)

    @classmethod
    def disarm_partition_a(cls, password: str) -> Self:
        """Cria comando para desarmar partição A.
        
        Args:
            password: Senha do usuário.
            
        Returns:
            Instância de DeactivationCommand.
        """
        return cls(password, partition=PartitionCode.PARTITION_A)

    @classmethod
    def disarm_partition_b(cls, password: str) -> Self:
        """Cria comando para desarmar partição B.
        
        Args:
            password: Senha do usuário.
            
        Returns:
            Instância de DeactivationCommand.
        """
        return cls(password, partition=PartitionCode.PARTITION_B)

    @classmethod
    def disarm_partition_c(cls, password: str) -> Self:
        """Cria comando para desarmar partição C.
        
        Args:
            password: Senha do usuário.
            
        Returns:
            Instância de DeactivationCommand.
        """
        return cls(password, partition=PartitionCode.PARTITION_C)

    @classmethod
    def disarm_partition_d(cls, password: str) -> Self:
        """Cria comando para desarmar partição D.
        
        Args:
            password: Senha do usuário.
            
        Returns:
            Instância de DeactivationCommand.
        """
        return cls(password, partition=PartitionCode.PARTITION_D)

    def __repr__(self) -> str:
        partition_str = self._partition.name if self._partition else "ALL"
        return f"DeactivationCommand(password='****', partition={partition_str})"



