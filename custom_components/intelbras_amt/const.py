"""Constantes para o componente Intelbras AMT."""

DOMAIN = "intelbras_amt"

# Configuração
CONF_PORT = "port"
CONF_PASSWORD = "password"
CONF_UPDATE_INTERVAL = "update_interval"

# Defaults
DEFAULT_PORT = 9009
DEFAULT_UPDATE_INTERVAL = 5
"""Intervalo padrão de atualização do status em segundos."""

# Atributos
ATTR_CONNECTED = "connected"
ATTR_LAST_HEARTBEAT = "last_heartbeat"
