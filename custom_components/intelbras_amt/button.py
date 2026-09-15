"""Limpeza manual da memória de disparos da central."""

import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, CONF_COMPUTER_PASSWORD
from .lib.protocol.programming import PROGRAMMING_MODELS, ProgrammingSession

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    async_add_entities([AMTClearAlarmButton(coordinator, entry)])


class AMTClearAlarmButton(CoordinatorEntity, ButtonEntity):
    _attr_has_entity_name = True
    _attr_name = "Limpar disparo (beta)"
    _attr_icon = "mdi:alarm-light-off"

    def __init__(self, coordinator, entry):
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_limpar_disparo"
        self._pressing = False

    @property
    def device_info(self):
        return {"identifiers": {(DOMAIN, self._entry.entry_id)}}

    @property
    def available(self):
        status = self.coordinator.data
        return bool(
            super().available and self.coordinator.connection_id and status
            and status.model in PROGRAMMING_MODELS
            and self._entry.data.get(CONF_COMPUTER_PASSWORD)
            and not status.armed and not status.partitions.any_armed and not status.siren_on
        )

    async def async_press(self):
        if self._pressing:
            raise HomeAssistantError("Limpeza de disparo já em andamento")
        self._pressing = True
        coordinator = self.coordinator
        connection_id = coordinator.connection_id
        try:
            # Atualiza antes de permitir a ação; não confiar em status antigo.
            await coordinator.async_refresh()
            if not self.available or coordinator.connection_id != connection_id:
                raise HomeAssistantError("Limpeza exige senha do computador configurada, central compatível conectada, todas as partições desarmadas e sirene desligada")
            async with coordinator.programming_lock:
                if coordinator.connection_id != connection_id:
                    raise HomeAssistantError("A conexão mudou durante a limpeza")
                async with ProgrammingSession(
                    coordinator.programming_host(), self._entry.data[CONF_COMPUTER_PASSWORD],
                ) as session:
                    await session.clear_alarm_memory()
            await coordinator.async_refresh()
            status = coordinator.data
            if (not coordinator.last_update_success or coordinator.connection_id != connection_id
                    or not status or status.triggered or status.zones.violated_zones):
                raise HomeAssistantError("Comando recebido, mas a nova leitura não confirmou a limpeza dos disparos")
            _LOGGER.info("Limpeza da memória de disparos confirmada pela central")
        except PermissionError as err:
            raise HomeAssistantError("A central rejeitou a senha do computador. Revise-a em Reconfigurar → Limpar disparo") from err
        except ValueError as err:
            raise HomeAssistantError(str(err)) from err
        except OSError as err:
            raise HomeAssistantError("Operação não confirmada; verifique a conexão local com a central e o estado antes de tentar novamente") from err
        finally:
            self._pressing = False
