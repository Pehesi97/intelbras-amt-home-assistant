"""Sensors para informações de status da central."""

import logging
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from homeassistant.components.sensor import SensorEntity, SensorStateClass, SensorDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .coordinator import AMTCoordinator
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Configura os sensors."""
    coordinator: AMTCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    
    entities: list[SensorEntity] = [
        AMTModelSensor(coordinator, entry),
        AMTFirmwareSensor(coordinator, entry),
        AMTDateTimeSensor(coordinator, entry),
        AMTZonesOpenSensor(coordinator, entry),
        AMTZonesViolatedSensor(coordinator, entry),
        AMTZonesBypassedSensor(coordinator, entry),
        AMTSirenStatusSensor(coordinator, entry),
        AMTArmedStatusSensor(coordinator, entry),
    ]
    
    async_add_entities(entities)


class AMTBaseSensor(CoordinatorEntity[AMTCoordinator], SensorEntity):
    """Base class para sensors da central."""
    
    _attr_has_entity_name = True
    
    def __init__(
        self,
        coordinator: AMTCoordinator,
        entry: ConfigEntry,
        unique_id_suffix: str,
        name: str,
    ) -> None:
        """Inicializa o sensor base.
        
        Args:
            coordinator: Coordinator do status.
            entry: Config entry.
            unique_id_suffix: Sufixo para o unique_id.
            name: Nome do sensor.
        """
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_{unique_id_suffix}"
        self._attr_name = name
    
    @property
    def device_info(self):
        """Informações do dispositivo."""
        return {
            "identifiers": {(DOMAIN, self._entry.entry_id)},
            "name": "Intelbras AMT 2018 / 4010",
            "manufacturer": "Intelbras",
            "model": "AMT 2018 / 4010",
        }


class AMTModelSensor(AMTBaseSensor):
    """Sensor para modelo da central."""
    
    def __init__(self, coordinator: AMTCoordinator, entry: ConfigEntry) -> None:
        """Inicializa o sensor de modelo."""
        super().__init__(coordinator, entry, "modelo", "Modelo")
        self._attr_icon = "mdi:chip"
    
    @property
    def native_value(self) -> str | None:
        """Retorna o modelo."""
        if not self.coordinator.data:
            return None
        
        # Importa o enum de modelos
        from .lib.const import CentralModel
        return CentralModel.get_name(self.coordinator.data.model)


class AMTFirmwareSensor(AMTBaseSensor):
    """Sensor para versão do firmware."""
    
    def __init__(self, coordinator: AMTCoordinator, entry: ConfigEntry) -> None:
        """Inicializa o sensor de firmware."""
        super().__init__(coordinator, entry, "firmware", "Firmware")
        self._attr_icon = "mdi:information"
    
    @property
    def native_value(self) -> str | None:
        """Retorna a versão do firmware."""
        if not self.coordinator.data:
            return None
        return f"v{self.coordinator.data.firmware_version}"


class AMTDateTimeSensor(AMTBaseSensor):
    """Sensor para data/hora da central."""
    
    def __init__(self, coordinator: AMTCoordinator, entry: ConfigEntry) -> None:
        """Inicializa o sensor de data/hora."""
        super().__init__(coordinator, entry, "data_hora", "Data/Hora")
        self._attr_icon = "mdi:clock"
        self._attr_device_class = SensorDeviceClass.TIMESTAMP
    
    @property
    def native_value(self) -> datetime | None:
        """Retorna a data/hora com timezone."""
        if not self.coordinator.data:
            return None
        
        # Pega o datetime da central
        central_dt = self.coordinator.data.central_datetime
        if central_dt is None:
            return None
        
        # Se já tem timezone, retorna direto
        if central_dt.tzinfo is not None:
            return central_dt
        
        # A central reporta horário local sem timezone
        # Assumimos que é o timezone do Home Assistant
        return central_dt.replace(tzinfo=dt_util.get_default_time_zone())


class AMTZonesOpenSensor(AMTBaseSensor):
    """Sensor para contagem de zonas abertas."""
    
    def __init__(self, coordinator: AMTCoordinator, entry: ConfigEntry) -> None:
        """Inicializa o sensor de zonas abertas."""
        super().__init__(coordinator, entry, "zonas_abertas", "Zonas Abertas")
        self._attr_icon = "mdi:door-open"
        self._attr_state_class = SensorStateClass.MEASUREMENT
    
    @property
    def native_value(self) -> int | None:
        """Retorna o número de zonas abertas."""
        if not self.coordinator.data:
            return None
        return len(self.coordinator.data.zones.open_zones)
    
    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Atributos extras com lista de zonas."""
        if not self.coordinator.data:
            return {}
        return {
            "zonas": sorted(self.coordinator.data.zones.open_zones),
        }


class AMTZonesViolatedSensor(AMTBaseSensor):
    """Sensor para lista de zonas violadas."""
    
    def __init__(self, coordinator: AMTCoordinator, entry: ConfigEntry) -> None:
        """Inicializa o sensor de zonas violadas."""
        super().__init__(coordinator, entry, "zonas_violadas", "Zonas Violadas")
        self._attr_icon = "mdi:alert"
        # Remove state_class pois agora é uma string, não uma medida
    
    @property
    def native_value(self) -> str | None:
        """Retorna a lista de zonas violadas como string."""
        if not self.coordinator.data:
            return None
        
        violated_zones = sorted(self.coordinator.data.zones.violated_zones)
        
        if not violated_zones:
            return "Nenhuma"
        
        # Retorna como string separada por vírgula: "26" ou "26, 30, 45"
        return ", ".join(str(zone) for zone in violated_zones)
    
    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Atributos extras com lista de zonas e contagem."""
        if not self.coordinator.data:
            return {}
        
        violated_zones = sorted(self.coordinator.data.zones.violated_zones)
        return {
            "zonas": violated_zones,
            "total": len(violated_zones),
        }


class AMTZonesBypassedSensor(AMTBaseSensor):
    """Sensor para contagem de zonas em bypass."""
    
    def __init__(self, coordinator: AMTCoordinator, entry: ConfigEntry) -> None:
        """Inicializa o sensor de zonas em bypass."""
        super().__init__(coordinator, entry, "zonas_bypass", "Zonas em Bypass")
        self._attr_icon = "mdi:shield-off"
        self._attr_state_class = SensorStateClass.MEASUREMENT
    
    @property
    def native_value(self) -> int | None:
        """Retorna o número de zonas em bypass."""
        if not self.coordinator.data:
            return None
        return len(self.coordinator.data.zones.bypassed_zones)
    
    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Atributos extras com lista de zonas."""
        if not self.coordinator.data:
            return {}
        return {
            "zonas": sorted(self.coordinator.data.zones.bypassed_zones),
        }


class AMTSirenStatusSensor(AMTBaseSensor):
    """Sensor para status da sirene."""
    
    def __init__(self, coordinator: AMTCoordinator, entry: ConfigEntry) -> None:
        """Inicializa o sensor de sirene."""
        super().__init__(coordinator, entry, "sirene", "Sirene")
        self._attr_icon = "mdi:bell"
    
    @property
    def native_value(self) -> str | None:
        """Retorna o status da sirene."""
        if not self.coordinator.data:
            return None
        return "Ligada" if self.coordinator.data.siren_on else "Desligada"


class AMTArmedStatusSensor(AMTBaseSensor):
    """Sensor para status de armamento geral."""
    
    def __init__(self, coordinator: AMTCoordinator, entry: ConfigEntry) -> None:
        """Inicializa o sensor de armamento."""
        super().__init__(coordinator, entry, "armada", "Armada")
        self._attr_icon = "mdi:shield-lock"
    
    @property
    def native_value(self) -> str | None:
        """Retorna o status de armamento."""
        if not self.coordinator.data:
            return None
        return "Armada" if self.coordinator.data.armed else "Desarmada"
    
    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Atributos extras com status das partições."""
        if not self.coordinator.data:
            return {}
        
        partitions = self.coordinator.data.partitions
        return {
            "particoes_habilitadas": partitions.partitions_enabled,
            "particao_a": "Armada" if partitions.partition_a_armed else "Desarmada",
            "particao_b": "Armada" if partitions.partition_b_armed else "Desarmada",
            "particao_c": "Armada" if partitions.partition_c_armed else "Desarmada",
            "particao_d": "Armada" if partitions.partition_d_armed else "Desarmada",
        }



