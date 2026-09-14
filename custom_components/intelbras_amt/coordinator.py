"""Coordinator para atualização periódica do status da central."""

import logging
import time
from datetime import datetime, timedelta, timezone

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
from .const import DEFAULT_UPDATE_INTERVAL

_LOGGER = logging.getLogger(__name__)

# Intervalo mínimo entre refreshes disparados por heartbeat (debounce)
_MIN_HEARTBEAT_REFRESH_INTERVAL = 2.0
"""Intervalo mínimo (em segundos) entre refreshes disparados por heartbeat."""


def _status_error(response, kind):
    message = f"Erro ao buscar status {kind}: {response.message} (0x{response.code:02X})"
    if response.response_type == ResponseType.NACK and response.code in (0xE1, 0xE2):
        message += (
            ". Confira a senha para consulta de status em Reconfigurar; "
            "na AMT 4010, a consulta pode exigir a senha do computador."
        )
    return UpdateFailed(message)


class AMTCoordinator(DataUpdateCoordinator[PartialCentralStatus | CentralStatus | None]):
    """Coordinator para atualizar status da central periodicamente.
    
    Detecta automaticamente o modelo da central e usa o comando apropriado:
    - AMT 2018 E/EG (0x1E): Comando 0x5A (status parcial, 43 bytes)
    - AMT 2018 E SMART (0x34): Comando 0x5A (status parcial, 43 bytes)
    - AMT 1000 Smart (0x36): Comando 0x5A (status parcial, 43 bytes)
    - AMT 4010 (0x41): Comando 0x5B (status completo, 54 bytes)
    
    Suporta refresh imediato ao receber heartbeat da central,
    reduzindo a latência de atualização para ~1-2 segundos.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        server: AMTServer,
        connection_id: str | None,
        password: str,
        entry_id: str,
        update_interval: int = DEFAULT_UPDATE_INTERVAL,
    ) -> None:
        """Inicializa o coordinator.
        
        Args:
            hass: Instância do Home Assistant.
            server: Servidor AMT.
            connection_id: ID da conexão ativa.
            password: Senha para consulta de status (independente dos comandos).
            entry_id: ID da config entry.
            update_interval: Intervalo de polling em segundos (padrão: 5s).
        """
        super().__init__(
            hass,
            _LOGGER,
            name=f"Intelbras AMT ({entry_id})",
            update_interval=timedelta(seconds=update_interval),
            config_entry=hass.config_entries.async_get_entry(entry_id),
        )
        self.server = server
        self.connection_id = connection_id
        self.password = password
        self.entry_id = entry_id
        self._detected_model: int | None = None
        """Modelo detectado da central (0x1E = AMT 2018 E/EG, 0x34 = AMT 2018 E SMART, 0x41 = AMT 4010)."""
        self.last_successful_poll: datetime | None = None
        self.successful_polls = 0
        self.failed_polls = 0
        self.last_error_type: str | None = None
        self._last_heartbeat_refresh: float = 0.0
        """Timestamp do último refresh disparado por heartbeat (monotonic)."""

    async def async_heartbeat_refresh(self) -> None:
        """Agenda um refresh de status ao receber heartbeat.
        
        Implementa debounce: ignora se o último refresh por heartbeat
        foi há menos de _MIN_HEARTBEAT_REFRESH_INTERVAL segundos.
        Isso evita spam de requests se heartbeats chegarem em rajada.
        """
        now = time.monotonic()
        elapsed = now - self._last_heartbeat_refresh
        
        if elapsed < _MIN_HEARTBEAT_REFRESH_INTERVAL:
            _LOGGER.debug(
                "Heartbeat refresh ignorado (debounce): último há %.1fs, mínimo %.1fs",
                elapsed,
                _MIN_HEARTBEAT_REFRESH_INTERVAL,
            )
            return
        
        self._last_heartbeat_refresh = now
        _LOGGER.debug("Heartbeat recebido, disparando refresh de status")
        await self.async_request_refresh()

    async def _async_update_data(self) -> PartialCentralStatus | CentralStatus | None:
        """Busca status atual da central.
        
        Detecta automaticamente o modelo no primeiro request e usa o comando apropriado.
        
        Returns:
            Status válido da central (parcial ou completo).
            
        Raises:
            UpdateFailed: Se houver erro ao buscar status.
        """
        if not self.connection_id:
            _LOGGER.debug("Central não conectada, não é possível atualizar status")
            raise UpdateFailed("Central desconectada")

        connection_id = self.connection_id
        try:
            # Se ainda não detectamos o modelo, tenta 0x5A primeiro (AMT 2018 E/EG/E SMART)
            if self._detected_model is None:
                _LOGGER.info("Detectando modelo da central automaticamente...")
                status = await self._detect_and_fetch_status()
            
            # Modelo já detectado, usa o comando apropriado
            elif self._detected_model in (
                CentralModel.AMT_2018_E,
                CentralModel.AMT_2018_E_SMART,
                CentralModel.AMT_1000_SMART,
            ):
                status = await self._fetch_partial_status()
            elif self._detected_model == CentralModel.AMT_4010:
                status = await self._fetch_full_status()
            else:
                _LOGGER.warning(f"Modelo desconhecido (0x{self._detected_model:02X}), tentando status parcial")
                status = await self._fetch_partial_status()
                
            if self.connection_id != connection_id:
                raise UpdateFailed("Conexão substituída durante a consulta")
            self.last_successful_poll = datetime.now(timezone.utc)
            self.successful_polls += 1
            self.last_error_type = None
            return status

        except TimeoutError as err:
            self.failed_polls += 1
            self.last_error_type = type(err).__name__
            raise UpdateFailed(f"Timeout aguardando resposta: {err}")
        except Exception as err:
            self.failed_polls += 1
            self.last_error_type = type(err).__name__
            raise UpdateFailed(f"Erro ao atualizar status: {err}")
    
    async def _detect_and_fetch_status(self) -> PartialCentralStatus | CentralStatus | None:
        """Detecta o modelo da central e busca o status apropriado.
        
        Tenta status parcial (0x5A) primeiro. Se receber resposta válida,
        detecta o modelo e decide qual comando usar nas próximas vezes.
        """
        # Tenta status parcial (0x5A) - AMT 2018 E/EG/E SMART
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
            raise _status_error(response, "parcial")
    
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
            raise _status_error(response, "completo")
