"""Gerenciador de conexões com centrais AMT.

Mantém o registro de todas as conexões ativas e permite
enviar comandos para centrais específicas ou todas ao mesmo tempo.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


logger = logging.getLogger(__name__)


@dataclass
class AMTConnection:
    """Representa uma conexão com uma central AMT.
    
    Attributes:
        id: Identificador único da conexão (IP:porta).
        address: Tupla (host, port) do endereço remoto.
        reader: StreamReader asyncio para leitura.
        writer: StreamWriter asyncio para escrita.
        connected_at: Timestamp da conexão.
        pending_response: Future aguardando resposta.
        metadata: Dados adicionais da conexão.
    """
    
    id: str
    address: tuple[str, int]
    reader: asyncio.StreamReader
    writer: asyncio.StreamWriter
    connected_at: datetime = field(default_factory=datetime.now)
    pending_response: asyncio.Future | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def host(self) -> str:
        """Endereço IP da central."""
        return self.address[0]

    @property
    def port(self) -> int:
        """Porta da conexão."""
        return self.address[1]

    @property
    def is_connected(self) -> bool:
        """Verifica se a conexão está ativa."""
        return not self.writer.is_closing()

    async def close(self) -> None:
        """Fecha a conexão."""
        if not self.writer.is_closing():
            self.writer.close()
            try:
                await self.writer.wait_closed()
            except Exception:
                pass

    def __repr__(self) -> str:
        return f"AMTConnection(id='{self.id}', connected_at={self.connected_at})"


class ConnectionManager:
    """Gerencia múltiplas conexões de centrais AMT.
    
    Permite registrar, buscar e remover conexões, além de
    manter estatísticas de uso.
    
    Example:
        ```python
        manager = ConnectionManager()
        
        # Adicionar conexão
        manager.add(connection)
        
        # Buscar conexão
        conn = manager.get("192.168.1.100:12345")
        
        # Listar todas
        for conn_id, conn in manager.all().items():
            print(f"{conn_id}: {conn.host}")
        ```
    """

    def __init__(self) -> None:
        """Inicializa o gerenciador de conexões."""
        self._connections: dict[str, AMTConnection] = {}
        self._lock = asyncio.Lock()

    @property
    def count(self) -> int:
        """Número de conexões ativas."""
        return len(self._connections)

    def add(self, connection: AMTConnection) -> None:
        """Adiciona uma nova conexão.
        
        Args:
            connection: Conexão a ser adicionada.
        """
        self._connections[connection.id] = connection
        logger.debug(f"Conexão adicionada: {connection.id}")

    def remove(self, connection_id: str) -> AMTConnection | None:
        """Remove uma conexão pelo ID.
        
        Args:
            connection_id: ID da conexão a remover.
            
        Returns:
            Conexão removida ou None se não existir.
        """
        connection = self._connections.pop(connection_id, None)
        if connection:
            logger.debug(f"Conexão removida: {connection_id}")
        return connection

    def get(self, connection_id: str) -> AMTConnection | None:
        """Busca uma conexão pelo ID.
        
        Args:
            connection_id: ID da conexão.
            
        Returns:
            Conexão ou None se não existir.
        """
        return self._connections.get(connection_id)

    def get_by_host(self, host: str) -> AMTConnection | None:
        """Busca uma conexão pelo endereço IP.
        
        Útil quando você sabe o IP da central mas não a porta.
        Retorna a primeira conexão encontrada para o host.
        
        Args:
            host: Endereço IP da central.
            
        Returns:
            Conexão ou None se não existir.
        """
        for connection in self._connections.values():
            if connection.host == host:
                return connection
        return None

    def all(self) -> dict[str, AMTConnection]:
        """Retorna todas as conexões.
        
        Returns:
            Dicionário {id: connection}.
        """
        return self._connections.copy()

    def list_hosts(self) -> list[str]:
        """Lista os endereços IP de todas as conexões.
        
        Returns:
            Lista de IPs conectados.
        """
        return [conn.host for conn in self._connections.values()]

    def has_connection(self, connection_id: str) -> bool:
        """Verifica se uma conexão existe.
        
        Args:
            connection_id: ID da conexão.
            
        Returns:
            True se existir.
        """
        return connection_id in self._connections

    def has_host(self, host: str) -> bool:
        """Verifica se há conexão com um host específico.
        
        Args:
            host: Endereço IP.
            
        Returns:
            True se existir conexão.
        """
        return any(conn.host == host for conn in self._connections.values())

    async def close_all(self) -> None:
        """Fecha todas as conexões."""
        async with self._lock:
            for connection in list(self._connections.values()):
                try:
                    await connection.close()
                except Exception as e:
                    logger.error(f"Erro ao fechar conexão {connection.id}: {e}")
            self._connections.clear()
        logger.info("Todas as conexões fechadas")

    async def close_connection(self, connection_id: str) -> bool:
        """Fecha uma conexão específica.
        
        Args:
            connection_id: ID da conexão.
            
        Returns:
            True se a conexão foi fechada.
        """
        connection = self.get(connection_id)
        if not connection:
            return False
        
        try:
            await connection.close()
            self.remove(connection_id)
            return True
        except Exception as e:
            logger.error(f"Erro ao fechar conexão {connection_id}: {e}")
            return False

    def get_stats(self) -> dict[str, Any]:
        """Retorna estatísticas do gerenciador.
        
        Returns:
            Dicionário com estatísticas.
        """
        return {
            "total_connections": self.count,
            "hosts": self.list_hosts(),
            "connections": [
                {
                    "id": conn.id,
                    "host": conn.host,
                    "port": conn.port,
                    "connected_at": conn.connected_at.isoformat(),
                    "is_connected": conn.is_connected,
                }
                for conn in self._connections.values()
            ],
        }

    def __len__(self) -> int:
        """Retorna o número de conexões."""
        return self.count

    def __contains__(self, connection_id: str) -> bool:
        """Verifica se uma conexão existe."""
        return self.has_connection(connection_id)

    def __iter__(self):
        """Itera sobre as conexões."""
        return iter(self._connections.values())

    def __repr__(self) -> str:
        return f"ConnectionManager(connections={self.count})"

