"""Instalação, reconfiguração e seleção de entidades pela interface do HA."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    DOMAIN, CONF_PASSWORD, CONF_STATUS_PASSWORD, CONF_PORT, CONF_UPDATE_INTERVAL,
    DEFAULT_PORT, DEFAULT_UPDATE_INTERVAL,
)
from .lib.const import CentralModel


def _connection_schema(defaults, reconfigure=False):
    password_field = vol.Optional(CONF_PASSWORD) if reconfigure else vol.Required(CONF_PASSWORD)
    fields = {
        vol.Required(CONF_PORT, default=defaults.get(CONF_PORT, DEFAULT_PORT)): int,
        password_field: selector.TextSelector(selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)),
        vol.Optional(CONF_STATUS_PASSWORD): selector.TextSelector(selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)),
    }
    if not reconfigure:
        fields[vol.Required(CONF_UPDATE_INTERVAL, default=DEFAULT_UPDATE_INTERVAL)] = int
    return vol.Schema(fields)


def _connection_errors(data):
    errors = {}
    port = data.get(CONF_PORT)
    interval = data.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL)
    if type(port) is not int or not 1 <= port <= 65535:
        errors[CONF_PORT] = "invalid_port"
    for key in (CONF_PASSWORD, CONF_STATUS_PASSWORD):
        password = data.get(key, "")
        if key == CONF_STATUS_PASSWORD and password == "":
            continue
        if not isinstance(password, str) or not (4 <= len(password) <= 6 and password.isascii() and password.isdigit()):
            errors[key] = "invalid_password"
    if type(interval) is not int or not 1 <= interval <= 60:
        errors[CONF_UPDATE_INTERVAL] = "invalid_update_interval"
    return errors


class IntelbrasAMTConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return IntelbrasAMTOptionsFlow()

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        errors = {}
        if user_input is not None:
            errors = _connection_errors(user_input)
            if not errors:
                port = user_input[CONF_PORT]
                await self.async_set_unique_id(f"intelbras_amt_{port}")
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=f"AMT 2018 / 4010 (:{port})", data=user_input)
        return self.async_show_form(step_id="user", data_schema=_connection_schema(user_input or {}), errors=errors)

    async def async_step_reconfigure(self, user_input=None):
        entry = self._get_reconfigure_entry()
        errors = {}
        if user_input is not None:
            data = {**entry.data, CONF_PORT: user_input.get(CONF_PORT)}
            # Campo vazio mantém a senha atual; ela nunca é preenchida no formulário.
            for key in (CONF_PASSWORD, CONF_STATUS_PASSWORD):
                if user_input.get(key):
                    data[key] = user_input[key]
            errors = _connection_errors(data)
            if any(other.entry_id != entry.entry_id and other.data.get(CONF_PORT) == data[CONF_PORT]
                   for other in self._async_current_entries()):
                errors[CONF_PORT] = "port_in_use"
            if not errors:
                return self.async_update_reload_and_abort(
                    entry, data_updates=data, unique_id=f"intelbras_amt_{data[CONF_PORT]}",
                )
        return self.async_show_form(
            step_id="reconfigure", data_schema=_connection_schema(user_input or entry.data, True), errors=errors,
        )


class IntelbrasAMTOptionsFlow(config_entries.OptionsFlowWithReload):
    async def async_step_init(self, user_input=None):
        entry = self.config_entry
        coordinator = self.hass.data.get(DOMAIN, {}).get(entry.entry_id, {}).get("coordinator")
        model = coordinator._detected_model if coordinator else None
        maximum = 64 if model is None or model == CentralModel.AMT_4010 else 48
        fields = {
            vol.Required(CONF_UPDATE_INTERVAL, default=entry.options.get(
                CONF_UPDATE_INTERVAL, entry.data.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL),
            )): vol.All(int, vol.Range(min=1, max=60)),
        }
        for key, limit, label in (("zones", maximum, "Zona"), ("pgms", 19, "PGM")):
            fields[vol.Required(key, default=[str(n) for n in entry.options.get(key, range(1, limit + 1)) if n <= limit])] = selector.SelectSelector(
                selector.SelectSelectorConfig(
                    multiple=True,
                    options=[{"value": str(n), "label": f"{label} {n:02d}"} for n in range(1, limit + 1)],
                ),
            )
        schema = vol.Schema(fields)
        errors = {}
        if user_input is not None:
            try:
                values = schema(user_input)
            except vol.Invalid:
                errors["base"] = "invalid_options"
            else:
                return self.async_create_entry(data={
                    **entry.options, CONF_UPDATE_INTERVAL: values[CONF_UPDATE_INTERVAL],
                    "zones": sorted({int(n) for n in values["zones"]}),
                    "pgms": sorted({int(n) for n in values["pgms"]}),
                })
        return self.async_show_form(step_id="init", data_schema=schema, errors=errors)
