"""Coordinator para atualização periódica do status da central."""

import logging
from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

# Importa da biblioteca local
from .lib.server import AMTServer
from .lib.protocol.commands import (
    PartialStatusRequestCommand,
    StatusRequestCommand,
    PartialCentralStatus,
    CentralStatus,
)
from .lib.protocol.responses import ResponseType
from .lib.const import CentralModel

_LOGGER = logging.getLogger(__name__)

UPDATE_INTERVAL = timedelta(seconds=30)
"""Intervalo de atualização do status (30 segundos)."""


class AMTCoordinator(DataUpdateCoordinator[PartialCentralStatus | CentralStatus | None]):
    """Coordinator para atualizar status da central periodicamente.
    
    Detecta automaticamente o modelo da central e usa o comando apropriado:
    - AMT 2018 E/EG (0x1E): Comando 0x5A (status parcial, 43 bytes)
    - AMT 4010 (0x41): Comando 0x5B (status completo, 54 bytes)
    """

    def __init__(
        self,
        hass: HomeAssistant,
        server: AMTServer,
        connection_id: str | None,
        password: str,
        entry_id: str,
    ) -> None:
        """Inicializa o coordinator.
        
        Args:
            hass: Instância do Home Assistant.
            server: Servidor AMT.
            connection_id: ID da conexão ativa.
            password: Senha da central.
            entry_id: ID da config entry.
        """
        super().__init__(
            hass,
            _LOGGER,
            name=f"Intelbras AMT ({entry_id})",
            update_interval=UPDATE_INTERVAL,
        )
        self.server = server
        self.connection_id = connection_id
        self.password = password
        self.entry_id = entry_id
        self._detected_model: int | None = None
        """Modelo detectado da central (0x1E = AMT 2018, 0x41 = AMT 4010)."""

    async def _async_update_data(self) -> PartialCentralStatus | CentralStatus | None:
        """Busca status atual da central.
        
        Detecta automaticamente o modelo no primeiro request e usa o comando apropriado.
        
        Returns:
            Status da central (parcial ou completo) ou None se não conectada.
            
        Raises:
            UpdateFailed: Se houver erro ao buscar status.
        """
        if not self.connection_id:
            _LOGGER.debug("Central não conectada, não é possível atualizar status")
            return None
        
        try:
            # Se ainda não detectamos o modelo, tenta 0x5A primeiro (AMT 2018)
            if self._detected_model is None:
                _LOGGER.info("Detectando modelo da central automaticamente...")
                return await self._detect_and_fetch_status()
            
            # Modelo já detectado, usa o comando apropriado
            if self._detected_model == CentralModel.AMT_2018_E:
                return await self._fetch_partial_status()
            elif self._detected_model == CentralModel.AMT_4010:
                return await self._fetch_full_status()
            else:
                _LOGGER.warning(f"Modelo desconhecido (0x{self._detected_model:02X}), tentando status parcial")
                return await self._fetch_partial_status()
                
        except TimeoutError as err:
            raise UpdateFailed(f"Timeout aguardando resposta: {err}")
        except Exception as err:
            raise UpdateFailed(f"Erro ao atualizar status: {err}")
    
    async def _detect_and_fetch_status(self) -> PartialCentralStatus | CentralStatus | None:
        """Detecta o modelo da central e busca o status apropriado.
        
        Tenta status parcial (0x5A) primeiro. Se receber resposta válida,
        detecta o modelo e decide qual comando usar nas próximas vezes.
        """
        # Tenta status parcial (0x5A) - AMT 2018 E/EG
        try:
            status = await self._fetch_partial_status()
            if status:
                self._detected_model = status.model
                model_name = CentralModel.get_name(self._detected_model)
                _LOGGER.info(f"Modelo detectado: {model_name} (0x{self._detected_model:02X})")
                
                # Se for AMT 4010, usa status completo nas próximas vezes
                if self._detected_model == CentralModel.AMT_4010:
                    _LOGGER.info("AMT 4010 detectado, mudando para comando 0x5B (status completo)")
                    return await self._fetch_full_status()
                
                return status
        except Exception as e:
            _LOGGER.debug(f"Status parcial falhou, tentando status completo: {e}")
        
        # Se falhar, tenta status completo (0x5B) - AMT 4010
        try:
            status = await self._fetch_full_status()
            if status:
                self._detected_model = status.model
                model_name = CentralModel.get_name(self._detected_model)
                _LOGGER.info(f"Modelo detectado: {model_name} (0x{self._detected_model:02X})")
                return status
        except Exception as e:
            raise UpdateFailed(f"Ambos comandos de status falharam: {e}")
        
        raise UpdateFailed("Não foi possível detectar o modelo da central")
    
    async def _fetch_partial_status(self) -> PartialCentralStatus | None:
        """Busca status parcial (0x5A) - 43 bytes."""
        cmd = PartialStatusRequestCommand(self.password)
        response = await self.server.send_command(
            self.connection_id,
            cmd.build_net_frame(),
            wait_response=True,
        )
        
        if response.response_type == ResponseType.DATA and len(response.raw_frame.content) >= 43:
            status = PartialCentralStatus.try_parse(response.raw_frame.content)
            if status:
                _LOGGER.debug("Status parcial atualizado")
                return status
            raise UpdateFailed("Não foi possível parsear status parcial")
        else:
            raise UpdateFailed(f"Erro ao buscar status parcial: {response.message}")
    
    async def _fetch_full_status(self) -> CentralStatus | None:
        """Busca status completo (0x5B) - 54 bytes."""
        cmd = StatusRequestCommand(self.password)
        response = await self.server.send_command(
            self.connection_id,
            cmd.build_net_frame(),
            wait_response=True,
        )
        
        if response.response_type == ResponseType.DATA and len(response.raw_frame.content) >= 54:
            status = CentralStatus.try_parse(response.raw_frame.content)
            if status:
                _LOGGER.debug("Status completo atualizado")
                return status
            raise UpdateFailed("Não foi possível parsear status completo")
        else:
            raise UpdateFailed(f"Erro ao buscar status completo: {response.message}")



