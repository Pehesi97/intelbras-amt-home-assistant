"""Switches para PGMs e controle de partições."""

import logging

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import AMTCoordinator
from .const import DOMAIN

# Importa da biblioteca local
from .lib.server import AMTServer
from .lib.protocol.commands import PGMCommand, ActivationCommand, DeactivationCommand, SirenCommand
from .lib.const import PartitionCode, PGMOutput

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Configura os switches."""
    coordinator: AMTCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    server: AMTServer = hass.data[DOMAIN][entry.entry_id]["server"]
    password: str = hass.data[DOMAIN][entry.entry_id]["password"]
    
    entities: list[SwitchEntity] = []
    
    # Switch geral para armar/desarmar todas as áreas
    entities.append(AMTGeneralArmSwitch(coordinator, entry, server, password))
    
    # Switch para controlar a sirene
    entities.append(AMTSirenSwitch(coordinator, entry, server, password))
    
    # Switches para PGMs (1-19)
    for pgm_num in range(1, 20):
        entities.append(AMTPGMSwitch(coordinator, entry, server, password, pgm_num))
    
    # Switches para armar/desarmar partições
    entities.append(AMTPartitionSwitch(coordinator, entry, server, password, "A"))
    entities.append(AMTPartitionSwitch(coordinator, entry, server, password, "B"))
    entities.append(AMTPartitionSwitch(coordinator, entry, server, password, "C"))
    entities.append(AMTPartitionSwitch(coordinator, entry, server, password, "D"))
    
    async_add_entities(entities)


class AMTGeneralArmSwitch(CoordinatorEntity[AMTCoordinator], SwitchEntity):
    """Switch geral para armar/desarmar todas as áreas.
    
    ON = Armada, OFF = Desarmada
    Este switch controla todas as áreas sem especificar partição.
    """
    
    _attr_has_entity_name = True
    _attr_icon = "mdi:shield-lock"
    
    def __init__(
        self,
        coordinator: AMTCoordinator,
        entry: ConfigEntry,
        server: AMTServer,
        password: str,
    ) -> None:
        """Inicializa o switch geral de armamento.
        
        Args:
            coordinator: Coordinator do status.
            entry: Config entry.
            server: Servidor AMT.
            password: Senha da central.
        """
        super().__init__(coordinator)
        self._entry = entry
        self._server = server
        self._password = password
        self._attr_unique_id = f"{entry.entry_id}_armar_geral"
        self._attr_name = "Armar Alarme"
    
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
    def is_on(self) -> bool:
        """Retorna se o alarme está armado (todas as áreas)."""
        if not self.coordinator.data:
            return False
        return self.coordinator.data.armed
    
    async def async_turn_on(self) -> None:
        """Arma todas as áreas."""
        connection_id = self.hass.data[DOMAIN][self._entry.entry_id].get("connection_id")
        if not connection_id:
            _LOGGER.error("Central não conectada, não é possível armar")
            return
        
        try:
            # Arma todas as áreas (sem especificar partição)
            cmd = ActivationCommand.arm_all(password=self._password)
            response = await self._server.send_command(
                connection_id,
                cmd.build_net_frame(),
                wait_response=True,
            )
            
            if response.is_success:
                _LOGGER.info("Alarme armado (todas as áreas) com sucesso")
                await self.coordinator.async_request_refresh()
            else:
                _LOGGER.error(f"Erro ao armar alarme: {response.message}")
        except Exception as e:
            _LOGGER.error(f"Erro ao armar alarme: {e}")
    
    async def async_turn_off(self) -> None:
        """Desarma todas as áreas."""
        connection_id = self.hass.data[DOMAIN][self._entry.entry_id].get("connection_id")
        if not connection_id:
            _LOGGER.error("Central não conectada, não é possível desarmar")
            return
        
        try:
            # Desarma todas as áreas
            cmd = DeactivationCommand.disarm_all(self._password)
            response = await self._server.send_command(
                connection_id,
                cmd.build_net_frame(),
                wait_response=True,
            )
            
            if response.is_success:
                _LOGGER.info("Alarme desarmado (todas as áreas) com sucesso")
                await self.coordinator.async_request_refresh()
            else:
                _LOGGER.error(f"Erro ao desarmar alarme: {response.message}")
        except Exception as e:
            _LOGGER.error(f"Erro ao desarmar alarme: {e}")


class AMTSirenSwitch(CoordinatorEntity[AMTCoordinator], SwitchEntity):
    """Switch para controlar a sirene.
    
    ON = Sirene ligada, OFF = Sirene desligada
    """
    
    _attr_has_entity_name = True
    _attr_icon = "mdi:bell"
    
    def __init__(
        self,
        coordinator: AMTCoordinator,
        entry: ConfigEntry,
        server: AMTServer,
        password: str,
    ) -> None:
        """Inicializa o switch de sirene.
        
        Args:
            coordinator: Coordinator do status.
            entry: Config entry.
            server: Servidor AMT.
            password: Senha da central.
        """
        super().__init__(coordinator)
        self._entry = entry
        self._server = server
        self._password = password
        self._attr_unique_id = f"{entry.entry_id}_sirene"
        self._attr_name = "Sirene"
    
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
    def is_on(self) -> bool:
        """Retorna se a sirene está ligada."""
        if not self.coordinator.data:
            return False
        return self.coordinator.data.siren_on
    
    async def async_turn_on(self) -> None:
        """Liga a sirene."""
        connection_id = self.hass.data[DOMAIN][self._entry.entry_id].get("connection_id")
        if not connection_id:
            _LOGGER.error("Central não conectada, não é possível ligar sirene")
            return
        
        try:
            cmd = SirenCommand.turn_on_siren(self._password)
            response = await self._server.send_command(
                connection_id,
                cmd.build_net_frame(),
                wait_response=True,
            )
            
            if response.is_success:
                _LOGGER.info("Sirene ligada com sucesso")
                await self.coordinator.async_request_refresh()
            else:
                _LOGGER.error(f"Erro ao ligar sirene: {response.message}")
        except Exception as e:
            _LOGGER.error(f"Erro ao ligar sirene: {e}")
    
    async def async_turn_off(self) -> None:
        """Desliga a sirene."""
        connection_id = self.hass.data[DOMAIN][self._entry.entry_id].get("connection_id")
        if not connection_id:
            _LOGGER.error("Central não conectada, não é possível desligar sirene")
            return
        
        try:
            cmd = SirenCommand.turn_off_siren(self._password)
            response = await self._server.send_command(
                connection_id,
                cmd.build_net_frame(),
                wait_response=True,
            )
            
            if response.is_success:
                _LOGGER.info("Sirene desligada com sucesso")
                await self.coordinator.async_request_refresh()
            else:
                _LOGGER.error(f"Erro ao desligar sirene: {response.message}")
        except Exception as e:
            _LOGGER.error(f"Erro ao desligar sirene: {e}")


class AMTPGMSwitch(CoordinatorEntity[AMTCoordinator], SwitchEntity):
    """Switch para controlar uma PGM."""
    
    _attr_has_entity_name = True
    
    def __init__(
        self,
        coordinator: AMTCoordinator,
        entry: ConfigEntry,
        server: AMTServer,
        password: str,
        pgm_number: int,
    ) -> None:
        """Inicializa o switch de PGM.
        
        Args:
            coordinator: Coordinator do status.
            entry: Config entry.
            server: Servidor AMT.
            password: Senha da central.
            pgm_number: Número da PGM (1-19).
        """
        super().__init__(coordinator)
        self.pgm_number = pgm_number
        self._entry = entry
        self._server = server
        self._password = password
        self._attr_unique_id = f"{entry.entry_id}_pgm_{pgm_number:02d}"
        self._attr_name = f"PGM {pgm_number:02d}"
    
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
    def is_on(self) -> bool:
        """Retorna se a PGM está ligada."""
        if not self.coordinator.data:
            return False
        return self.coordinator.data.pgm.is_on(self.pgm_number)
    
    async def async_turn_on(self) -> None:
        """Liga a PGM."""
        connection_id = self.hass.data[DOMAIN][self._entry.entry_id].get("connection_id")
        if not connection_id:
            _LOGGER.error("Central não conectada, não é possível ligar PGM")
            return
        
        try:
            pgm_output = PGMOutput(self.pgm_number)
            cmd = PGMCommand.turn_on(self._password, pgm_output)
            response = await self._server.send_command(
                connection_id,
                cmd.build_net_frame(),
                wait_response=True,
            )
            
            if response.is_success:
                _LOGGER.info(f"PGM {self.pgm_number} ligada com sucesso")
                await self.coordinator.async_request_refresh()
            else:
                _LOGGER.error(f"Erro ao ligar PGM {self.pgm_number}: {response.message}")
        except Exception as e:
            _LOGGER.error(f"Erro ao ligar PGM {self.pgm_number}: {e}")
    
    async def async_turn_off(self) -> None:
        """Desliga a PGM."""
        connection_id = self.hass.data[DOMAIN][self._entry.entry_id].get("connection_id")
        if not connection_id:
            _LOGGER.error("Central não conectada, não é possível desligar PGM")
            return
        
        try:
            pgm_output = PGMOutput(self.pgm_number)
            cmd = PGMCommand.turn_off(self._password, pgm_output)
            response = await self._server.send_command(
                connection_id,
                cmd.build_net_frame(),
                wait_response=True,
            )
            
            if response.is_success:
                _LOGGER.info(f"PGM {self.pgm_number} desligada com sucesso")
                await self.coordinator.async_request_refresh()
            else:
                _LOGGER.error(f"Erro ao desligar PGM {self.pgm_number}: {response.message}")
        except Exception as e:
            _LOGGER.error(f"Erro ao desligar PGM {self.pgm_number}: {e}")


class AMTPartitionSwitch(CoordinatorEntity[AMTCoordinator], SwitchEntity):
    """Switch para armar/desarmar uma partição.
    
    ON = Armada, OFF = Desarmada
    """
    
    _attr_has_entity_name = True
    _attr_icon = "mdi:shield-lock"
    
    def __init__(
        self,
        coordinator: AMTCoordinator,
        entry: ConfigEntry,
        server: AMTServer,
        password: str,
        partition: str,
    ) -> None:
        """Inicializa o switch de partição.
        
        Args:
            coordinator: Coordinator do status.
            entry: Config entry.
            server: Servidor AMT.
            password: Senha da central.
            partition: Partição ('A', 'B', 'C', 'D').
        """
        super().__init__(coordinator)
        self.partition = partition
        self._entry = entry
        self._server = server
        self._password = password
        self._attr_unique_id = f"{entry.entry_id}_particao_{partition}"
        self._attr_name = f"Partição {partition}"
    
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
    def is_on(self) -> bool:
        """Retorna se a partição está armada."""
        if not self.coordinator.data:
            return False
        
        partitions = self.coordinator.data.partitions
        
        if self.partition == "A":
            return partitions.partition_a_armed
        elif self.partition == "B":
            return partitions.partition_b_armed
        elif self.partition == "C":
            return partitions.partition_c_armed
        elif self.partition == "D":
            return partitions.partition_d_armed
        
        return False
    
    async def async_turn_on(self) -> None:
        """Arma a partição."""
        connection_id = self.hass.data[DOMAIN][self._entry.entry_id].get("connection_id")
        if not connection_id:
            _LOGGER.error("Central não conectada, não é possível armar partição")
            return
        
        try:
            # Mapeia partição para PartitionCode
            partition_map = {
                "A": PartitionCode.PARTITION_A,
                "B": PartitionCode.PARTITION_B,
                "C": PartitionCode.PARTITION_C,
                "D": PartitionCode.PARTITION_D,
            }
            partition_code = partition_map.get(self.partition)
            
            if partition_code:
                cmd = ActivationCommand(password=self._password, partition=partition_code)
            else:
                _LOGGER.error(f"Partição inválida: {self.partition}")
                return
            
            response = await self._server.send_command(
                connection_id,
                cmd.build_net_frame(),
                wait_response=True,
            )
            
            if response.is_success:
                _LOGGER.info(f"Partição {self.partition} armada com sucesso")
                await self.coordinator.async_request_refresh()
            else:
                _LOGGER.error(f"Erro ao armar partição {self.partition}: {response.message}")
        except Exception as e:
            _LOGGER.error(f"Erro ao armar partição {self.partition}: {e}")
    
    async def async_turn_off(self) -> None:
        """Desarma a partição."""
        connection_id = self.hass.data[DOMAIN][self._entry.entry_id].get("connection_id")
        if not connection_id:
            _LOGGER.error("Central não conectada, não é possível desarmar partição")
            return
        
        try:
            # Mapeia partição para método de desarme
            if self.partition == "A":
                cmd = DeactivationCommand.disarm_partition_a(self._password)
            elif self.partition == "B":
                cmd = DeactivationCommand.disarm_partition_b(self._password)
            elif self.partition == "C":
                cmd = DeactivationCommand.disarm_partition_c(self._password)
            elif self.partition == "D":
                cmd = DeactivationCommand.disarm_partition_d(self._password)
            else:
                _LOGGER.error(f"Partição inválida: {self.partition}")
                return
            
            response = await self._server.send_command(
                connection_id,
                cmd.build_net_frame(),
                wait_response=True,
            )
            
            if response.is_success:
                _LOGGER.info(f"Partição {self.partition} desarmada com sucesso")
                await self.coordinator.async_request_refresh()
            else:
                _LOGGER.error(f"Erro ao desarmar partição {self.partition}: {response.message}")
        except Exception as e:
            _LOGGER.error(f"Erro ao desarmar partição {self.partition}: {e}")

