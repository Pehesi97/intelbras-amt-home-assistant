"""Entidade Alarm Control Panel para Intelbras AMT 2018 / 4010."""

import logging
from datetime import datetime
from typing import Any

from homeassistant.components.alarm_control_panel import (
    AlarmControlPanelEntity,
    AlarmControlPanelEntityFeature,
    AlarmControlPanelState,
    CodeFormat,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

# Importa da biblioteca local
from .lib.server import AMTServer
from .lib.protocol.commands import ActivationCommand, DeactivationCommand
from .lib.const import PartitionCode

from .const import DOMAIN, CONF_PASSWORD, ATTR_CONNECTED, ATTR_LAST_HEARTBEAT
from .coordinator import AMTCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Configura a entidade alarm_control_panel."""
    coordinator: AMTCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    async_add_entities([IntelbrasAMTAlarm(hass, entry, coordinator)])


class IntelbrasAMTAlarm(CoordinatorEntity[AMTCoordinator], AlarmControlPanelEntity):
    """Representa o painel de alarme Intelbras AMT 2018 / 4010."""

    _attr_has_entity_name = True
    _attr_name = "Alarme"
    _attr_code_format = CodeFormat.NUMBER
    _attr_code_arm_required = False  # Usa senha salva na config
    _attr_supported_features = (
        AlarmControlPanelEntityFeature.ARM_HOME |
        AlarmControlPanelEntityFeature.ARM_AWAY
        # AlarmControlPanelEntityFeature.TRIGGER  # Quando implementarmos
    )

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        coordinator: AMTCoordinator,
    ) -> None:
        """Inicializa a entidade."""
        super().__init__(coordinator)
        self.hass = hass
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_alarm"
        
    @property
    def device_info(self):
        """Informações do dispositivo."""
        return {
            "identifiers": {(DOMAIN, self._entry.entry_id)},
            "name": "Intelbras AMT 2018 / 4010",
            "manufacturer": "Intelbras",
            "model": "AMT 2018 / 4010",
        }

    @property
    def alarm_state(self) -> AlarmControlPanelState | None:
        """Retorna o estado atual do alarme usando a nova API."""
        entry_data = self.hass.data.get(DOMAIN, {}).get(self._entry.entry_id, {})
        if not entry_data.get("connected", False):
            return None
        
        if not self.coordinator.data:
            return None
        
        status = self.coordinator.data
        
        # Verifica se está disparado
        if status.triggered:
            return AlarmControlPanelState.TRIGGERED
        
        # Verifica se está armada
        if status.armed:
            # Verifica se é stay mode (home) ou away
            if status.partitions.partitions_enabled:
                # Se partições estão habilitadas, verifica se alguma está em stay mode
                # Por enquanto, assumimos que se todas estão armadas, é away
                return AlarmControlPanelState.ARMED_AWAY
            else:
                # Sem partições, verifica se é stay mode
                # Por enquanto, assumimos away se armada
                return AlarmControlPanelState.ARMED_AWAY
        
        return AlarmControlPanelState.DISARMED

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Atributos extras."""
        entry_data = self.hass.data.get(DOMAIN, {}).get(self._entry.entry_id, {})
        attrs = {
            ATTR_CONNECTED: entry_data.get("connected", False),
            "connection_id": entry_data.get("connection_id"),
        }
        
        if self.coordinator.data:
            status = self.coordinator.data
            attrs.update({
                "sirene": "Ligada" if status.siren_on else "Desligada",
                "particoes_habilitadas": status.partitions.partitions_enabled,
                "particao_a": "Armada" if status.partitions.partition_a_armed else "Desarmada",
                "particao_b": "Armada" if status.partitions.partition_b_armed else "Desarmada",
            })
        
        return attrs

    async def async_alarm_arm_away(self, code: str | None = None) -> None:
        """Arma o alarme no modo away (todas as zonas)."""
        await self._arm_alarm(partition=None)

    async def async_alarm_arm_home(self, code: str | None = None) -> None:
        """Arma o alarme no modo home (stay)."""
        await self._arm_alarm(partition=PartitionCode.STAY_MODE)

    async def async_alarm_disarm(self, code: str | None = None) -> None:
        """Desarma o alarme."""
        entry_data = self.hass.data.get(DOMAIN, {}).get(self._entry.entry_id, {})
        server: AMTServer = entry_data.get("server")
        connection_id = entry_data.get("connection_id")
        password = entry_data.get("password", "")
        
        if not server or not connection_id:
            _LOGGER.error("Central não conectada, não é possível desarmar")
            return
        
        try:
            # Desarma todas as áreas
            cmd = DeactivationCommand.disarm_all(password)
            response = await server.send_command(
                connection_id,
                cmd.build_net_frame(),
                wait_response=True,
            )
            
            if response.is_success:
                _LOGGER.info("Alarme desarmado com sucesso!")
                await self.coordinator.async_request_refresh()
            else:
                _LOGGER.error(f"Erro ao desarmar alarme: {response.message}")
                
        except TimeoutError:
            _LOGGER.error("Timeout aguardando resposta da central")
        except Exception as e:
            _LOGGER.error(f"Erro ao enviar comando: {e}")

    async def _arm_alarm(self, partition: PartitionCode | None = None) -> None:
        """Envia comando de ativação para a central."""
        entry_data = self.hass.data.get(DOMAIN, {}).get(self._entry.entry_id, {})
        server: AMTServer = entry_data.get("server")
        connection_id = entry_data.get("connection_id")
        password = entry_data.get("password", "")
        
        if not server or not connection_id:
            _LOGGER.error("Central não conectada, não é possível armar")
            return
        
        # Cria comando de ativação
        if partition:
            cmd = ActivationCommand(password=password, partition=partition)
        else:
            cmd = ActivationCommand.arm_all(password=password)
        
        try:
            # Envia comando e aguarda resposta
            response = await server.send_command(
                connection_id,
                cmd.build_net_frame(),
                wait_response=True,
            )
            
            if response.is_success:
                _LOGGER.info("Alarme armado com sucesso!")
                await self.coordinator.async_request_refresh()
            else:
                _LOGGER.error(f"Erro ao armar alarme: {response.message}")
                
        except TimeoutError:
            _LOGGER.error("Timeout aguardando resposta da central")
        except Exception as e:
            _LOGGER.error(f"Erro ao enviar comando: {e}")

