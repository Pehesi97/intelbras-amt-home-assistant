"""Config flow para Intelbras AMT 2018 / 4010."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN, CONF_PASSWORD, CONF_PORT, DEFAULT_PORT


class IntelbrasAMTConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow para configurar Intelbras AMT via UI."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Primeiro passo: configuração pelo usuário."""
        errors: dict[str, str] = {}
        
        if user_input is not None:
            # Valida os dados
            port = user_input.get(CONF_PORT, DEFAULT_PORT)
            password = user_input.get(CONF_PASSWORD, "")
            
            if not isinstance(port, int) or not 1 <= port <= 65535:
                errors["port"] = "invalid_port"
            
            if not isinstance(password, str) or len(password) < 4 or len(password) > 6:
                errors["password"] = "invalid_password"
            
            if not errors:
                # Verifica se já existe uma entrada com a mesma porta
                await self.async_set_unique_id(f"intelbras_amt_{port}")
                self._abort_if_unique_id_configured()
                
                # Cria a config entry
                return self.async_create_entry(
                    title=f"AMT 2018 / 4010 (:{port})",
                    data={
                        CONF_PORT: port,
                        CONF_PASSWORD: password,
                    },
                )
        
        # Mostra o formulário
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Optional(CONF_PORT, default=DEFAULT_PORT): int,
                vol.Required(CONF_PASSWORD): str,
            }),
            errors=errors,
            description_placeholders={
                "default_port": str(DEFAULT_PORT),
            },
        )



