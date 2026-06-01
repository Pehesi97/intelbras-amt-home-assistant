"""Entidade Alarm Control Panel para Intelbras AMT 2018 / 4010."""

import logging
import time
from typing import Any

from homeassistant.components.alarm_control_panel import (
    AlarmControlPanelEntity,
    AlarmControlPanelEntityFeature,
    AlarmControlPanelState,
    CodeFormat,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

# Importa da biblioteca local
from .lib.server import AMTServer
from .lib.protocol.commands import ActivationCommand, DeactivationCommand
from .lib.const import PartitionCode

from .const import DOMAIN, CONF_PASSWORD, ATTR_CONNECTED, ATTR_LAST_HEARTBEAT
from .coordinator import AMTCoordinator

_LOGGER = logging.getLogger(__name__)

_SIREN_TRIGGER_FALLBACK_SECONDS = 4.0


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
        self._siren_on_since: float | None = None
        self._siren_trigger_confirmed = False
        self._last_trigger_reason: str | None = None
        self._last_ignored_triggered_raw: bytes | None = None

    @callback
    def _handle_coordinator_update(self) -> None:
        """Atualiza o fallback por sirene apenas com status novo da central."""
        self._update_siren_trigger_fallback()
        super()._handle_coordinator_update()

    def _update_siren_trigger_fallback(self) -> None:
        """Confirma sirene como disparo só após status sustentado."""
        status = self.coordinator.data
        if not status or not status.siren_on:
            self._siren_on_since = None
            self._siren_trigger_confirmed = False
            return

        now = time.monotonic()
        if self._siren_on_since is None:
            self._siren_on_since = now
            self._siren_trigger_confirmed = False
            return

        self._siren_trigger_confirmed = (
            now - self._siren_on_since >= _SIREN_TRIGGER_FALLBACK_SECONDS
        )

    def _trigger_reason(self) -> str | None:
        """Retorna o motivo para expor TRIGGERED, se houver."""
        status = self.coordinator.data
        if not status:
            return None

        if status.triggered and status.armed:
            return "triggered_armed"
        if status.triggered and status.siren_on:
            return "triggered_with_siren"
        if self._siren_trigger_confirmed:
            return "siren_sustained"
        return None

    def _function_byte(self) -> int | None:
        """Retorna o byte de funcionamento do status bruto, se disponível."""
        status = self.coordinator.data
        if not status:
            return None

        raw_data = status.raw_data
        if len(raw_data) == 43:
            return raw_data[22]
        if len(raw_data) == 54:
            return raw_data[29]
        return None

    def _log_trigger_decision(self, reason: str) -> None:
        """Loga por que o painel foi exposto como TRIGGERED."""
        if reason == self._last_trigger_reason:
            return

        self._last_trigger_reason = reason
        self._last_ignored_triggered_raw = None
        status = self.coordinator.data
        if not status:
            return

        _LOGGER.warning(
            "Alarme exposto como TRIGGERED: reason=%s armed=%s triggered=%s "
            "siren_on=%s func_byte=%s open_zones=%s violated_zones=%s raw=%s",
            reason,
            status.armed,
            status.triggered,
            status.siren_on,
            self._format_byte(self._function_byte()),
            sorted(status.zones.open_zones),
            sorted(status.zones.violated_zones),
            status.raw_data.hex(" "),
        )

    def _log_ignored_disarmed_triggered(self) -> None:
        """Loga quando o bit triggered é ignorado por não parecer disparo real."""
        status = self.coordinator.data
        if not status or not status.triggered:
            self._last_ignored_triggered_raw = None
            return

        raw_data = status.raw_data
        if raw_data == self._last_ignored_triggered_raw:
            return

        self._last_ignored_triggered_raw = raw_data
        _LOGGER.warning(
            "Ignorando bit triggered com central desarmada e sirene desligada: "
            "armed=%s triggered=%s siren_on=%s func_byte=%s open_zones=%s "
            "violated_zones=%s raw=%s",
            status.armed,
            status.triggered,
            status.siren_on,
            self._format_byte(self._function_byte()),
            sorted(status.zones.open_zones),
            sorted(status.zones.violated_zones),
            raw_data.hex(" "),
        )

    @staticmethod
    def _format_byte(value: int | None) -> str | None:
        """Formata byte para log."""
        if value is None:
            return None
        return f"0x{value:02X}"

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
        
        trigger_reason = self._trigger_reason()
        if trigger_reason:
            self._log_trigger_decision(trigger_reason)
            return AlarmControlPanelState.TRIGGERED

        self._last_trigger_reason = None
        if status.triggered:
            self._log_ignored_disarmed_triggered()
        else:
            self._last_ignored_triggered_raw = None
        
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
            await server.send_command(
                connection_id,
                cmd.build_net_frame(),
                wait_response=False,
            )
            _LOGGER.info("Comando de desarme enviado para a central")
                
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
            await server.send_command(
                connection_id,
                cmd.build_net_frame(),
                wait_response=False,
            )
            _LOGGER.info("Comando de arme enviado para a central")
                
        except TimeoutError:
            _LOGGER.error("Timeout aguardando resposta da central")
        except Exception as e:
            _LOGGER.error(f"Erro ao enviar comando: {e}")
