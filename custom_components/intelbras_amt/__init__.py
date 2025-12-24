"""Intelbras AMT 2018/4010 - Integração para Home Assistant.

Esta integração inicia um servidor TCP na porta 9009 que aguarda
a conexão da central de alarme Intelbras AMT 2018/4010.

A central conecta ativamente ao servidor e mantém a conexão aberta,
enviando heartbeats periodicamente.
"""

# Permite importar lib/ sem Home Assistant (para servidor standalone)
try:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.const import Platform
    from homeassistant.core import HomeAssistant
    _HAS_HOMEASSISTANT = True
except ImportError:
    # Modo standalone - sem Home Assistant
    # Não define funções de setup, mas permite importar o módulo
    _HAS_HOMEASSISTANT = False
    __all__ = []

# Só carrega código do HA se temos Home Assistant disponível
if _HAS_HOMEASSISTANT:
    import asyncio
    import logging
    import sys
    from datetime import datetime
    from pathlib import Path

    from .const import DOMAIN, CONF_PORT, CONF_PASSWORD, DEFAULT_PORT
    from .coordinator import AMTCoordinator

    _LOGGER = logging.getLogger(__name__)

    # Importa da biblioteca local
    from .lib.server import AMTServer, AMTServerConfig
    from .lib.protocol.isecnet import ISECNetFrame

    PLATFORMS: list[Platform] = [
        Platform.ALARM_CONTROL_PANEL,
        Platform.BINARY_SENSOR,
        Platform.SWITCH,
        Platform.SENSOR,
    ]

    async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
        """Configura a integração a partir de uma config entry.
        
        Este método é chamado quando o Home Assistant inicia ou quando
        a integração é adicionada. Aqui iniciamos o servidor TCP.
        """
        hass.data.setdefault(DOMAIN, {})
        
        port = entry.data.get(CONF_PORT, DEFAULT_PORT)
        password = entry.data.get(CONF_PASSWORD, "")
        
        # Cria configuração do servidor
        config = AMTServerConfig(
            host="0.0.0.0",
            port=port,
            auto_ack_heartbeat=True,
        )
        
        # Cria o servidor
        server = AMTServer(config)
        
        # Cria o coordinator para atualização periódica de status
        coordinator = AMTCoordinator(
            hass=hass,
            server=server,
            connection_id=None,  # Será atualizado quando conectar
            password=password,
            entry_id=entry.entry_id,
        )
        
        # Callbacks para eventos
        @server.on_connect
        async def on_central_connect(conn):
            """Chamado quando uma central conecta."""
            _LOGGER.info(f"Central AMT conectada: {conn.id}")
            entry_data = hass.data[DOMAIN][entry.entry_id]
            entry_data["connected"] = True
            entry_data["connection_id"] = conn.id
            entry_data["connected_at"] = datetime.now()
            
            # Atualiza o coordinator com a nova conexão
            coordinator.connection_id = conn.id
            
            # Dispara evento no HA
            hass.bus.async_fire(f"{DOMAIN}_connected", {"connection_id": conn.id})
        
        @server.on_disconnect
        async def on_central_disconnect(conn):
            """Chamado quando uma central desconecta."""
            _LOGGER.warning(f"Central AMT desconectada: {conn.id}")
            entry_data = hass.data[DOMAIN][entry.entry_id]
            entry_data["connected"] = False
            entry_data["connection_id"] = None
            
            # Atualiza o coordinator
            coordinator.connection_id = None
            
            # Dispara evento no HA
            hass.bus.async_fire(f"{DOMAIN}_disconnected", {"connection_id": conn.id})
        
        @server.on_frame
        async def on_frame_received(conn, frame: ISECNetFrame):
            """Chamado quando um frame é recebido (exceto heartbeat)."""
            _LOGGER.debug(f"Frame recebido de {conn.id}: {frame}")
            
            # Dispara evento no HA para que entidades possam reagir
            hass.bus.async_fire(f"{DOMAIN}_frame_received", {
                "connection_id": conn.id,
                "command": frame.command,
                "content": frame.content.hex(),
            })
        
        # Armazena dados no hass.data por entry_id
        hass.data[DOMAIN][entry.entry_id] = {
            "server": server,
            "password": password,
            "coordinator": coordinator,
            "connected": False,
            "connection_id": None,
        }
        
        # Inicia o servidor em background
        await server.start()
        _LOGGER.info(f"Servidor AMT iniciado na porta {port}")
        
        # Configura as plataformas (alarm_control_panel, binary_sensor, switch, sensor)
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
        
        return True

    async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
        """Descarrega a integração.
        
        Chamado quando o Home Assistant para ou quando a integração é removida.
        """
        # Descarrega plataformas
        unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
        
        if unload_ok:
            entry_data = hass.data[DOMAIN].get(entry.entry_id, {})
            
            # Para o servidor TCP
            server: AMTServer = entry_data.get("server")
            if server:
                await server.stop()
                _LOGGER.info("Servidor AMT parado")
            
            # Remove dados da entry
            hass.data[DOMAIN].pop(entry.entry_id, None)
            
            # Se não há mais entries, limpa o DOMAIN
            if not hass.data[DOMAIN]:
                hass.data.pop(DOMAIN)
        
        return unload_ok
