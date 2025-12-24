"""Constantes do protocolo ISECNet/ISECMobile."""

from enum import IntEnum


# =============================================================================
# Configurações de Rede
# =============================================================================

DEFAULT_PORT = 9009
"""Porta TCP padrão para comunicação ISECNet."""

RESPONSE_TIMEOUT = 8.0
"""Timeout máximo em segundos para aguardar resposta da central (Ethernet)."""

KEEPALIVE_INTERVAL = 30.0
"""Intervalo em segundos para envio de keep-alive."""


# =============================================================================
# Protocolo ISECNet
# =============================================================================

ISECNET_COMMAND_MOBILE = 0xE9
"""Comando ISECNet para encapsular frames ISECMobile."""

ISECNET_COMMAND_HEARTBEAT = 0xF7
"""Comando ISECNet para heartbeat (keep-alive)."""


# =============================================================================
# Protocolo ISECMobile
# =============================================================================

ISECMOBILE_FRAME_DELIMITER = 0x21
"""Delimitador de frame ISECMobile (caractere '!')."""

ISECMOBILE_PASSWORD_MIN_LEN = 4
"""Tamanho mínimo da senha em bytes."""

ISECMOBILE_PASSWORD_MAX_LEN = 6
"""Tamanho máximo da senha em bytes."""

ISECMOBILE_CONTENT_MAX_LEN = 52
"""Tamanho máximo do conteúdo em bytes."""


# =============================================================================
# Comandos ISECMobile
# =============================================================================

class CommandCode(IntEnum):
    """Códigos de comandos ISECMobile."""
    
    ACTIVATION = 0x41
    """Comando 0x41 - Ativação/Armar da central ou partição."""
    
    DEACTIVATION = 0x44
    """Comando 0x44 - Desativação/Desarmar da central ou partição."""
    
    PGM_CONTROL = 0x50
    """Comando 0x50 - Controle de PGM (ligar/desligar saída programável)."""
    
    SIREN_ON = 0x43
    """Comando 0x43 - Liga a sirene."""
    
    SIREN_OFF = 0x63
    """Comando 0x63 - Desliga a sirene."""
    
    STATUS_REQUEST_PARTIAL = 0x5A
    """Comando 0x5A - Solicita status parcial da central (retorna 43 bytes)."""
    
    STATUS_REQUEST = 0x5B
    """Comando 0x5B - Solicita status completo da central (retorna 54 bytes)."""


class PGMAction(IntEnum):
    """Ações para controle de PGM."""
    
    TURN_ON = 0x4C
    """Liga a PGM (0x4C = 'L')."""
    
    TURN_OFF = 0x44
    """Desliga a PGM (0x44 = 'D')."""


class PGMOutput(IntEnum):
    """Endereços de saída PGM (1 a 19)."""
    
    PGM_1 = 0x31
    PGM_2 = 0x32
    PGM_3 = 0x33
    PGM_4 = 0x34
    PGM_5 = 0x35
    PGM_6 = 0x36
    PGM_7 = 0x37
    PGM_8 = 0x38
    PGM_9 = 0x39
    PGM_10 = 0x3A
    PGM_11 = 0x3B
    PGM_12 = 0x3C
    PGM_13 = 0x3D
    PGM_14 = 0x3E
    PGM_15 = 0x3F
    PGM_16 = 0x40
    PGM_17 = 0x41
    PGM_18 = 0x42
    PGM_19 = 0x43
    
    @classmethod
    def from_number(cls, num: int) -> "PGMOutput":
        """Converte número da PGM (1-19) para o enum.
        
        Args:
            num: Número da PGM (1-19).
            
        Returns:
            Valor do enum correspondente.
            
        Raises:
            ValueError: Se o número estiver fora do range válido.
        """
        if num < 1 or num > 19:
            raise ValueError(f"Número de PGM inválido: {num}. Deve ser entre 1 e 19.")
        return cls(0x30 + num)


class PartitionCode(IntEnum):
    """Códigos de partição para comando de ativação."""
    
    ALL = 0x00
    """Ativa todas as partições (NULL - sem sub-comando)."""
    
    PARTITION_A = 0x41
    """Ativa partição A."""
    
    PARTITION_B = 0x42
    """Ativa partição B."""
    
    PARTITION_C = 0x43
    """Ativa partição C."""
    
    PARTITION_D = 0x44
    """Ativa partição D."""
    
    STAY_MODE = 0x50
    """Ativa no modo Stay."""


# =============================================================================
# Respostas ISECMobile
# =============================================================================

class ResponseCode(IntEnum):
    """Códigos de resposta ISECMobile."""
    
    # ACK - Sucesso
    ACK = 0xFE
    """Comando recebido e executado com sucesso."""
    
    # NACK - Erros
    NACK_INVALID_PACKET = 0xE0
    """Formato de pacote inválido."""
    
    NACK_WRONG_PASSWORD = 0xE1
    """Senha incorreta."""
    
    NACK_INVALID_COMMAND = 0xE2
    """Comando inválido."""
    
    NACK_NOT_PARTITIONED = 0xE3
    """Central não particionada."""
    
    NACK_ZONES_OPEN = 0xE4
    """Zonas abertas."""
    
    NACK_DISCONTINUED = 0xE5
    """Comando descontinuado."""
    
    NACK_NO_BYPASS_PERMISSION = 0xE6
    """Usuário sem permissão para bypass."""
    
    NACK_NO_DEACTIVATE_PERMISSION = 0xE7
    """Usuário sem permissão para desativar."""
    
    NACK_BYPASS_NOT_ALLOWED = 0xE8
    """Bypass não permitido com a central ativada."""
    
    NACK_NO_ZONES_IN_PARTITION = 0xEA
    """Partição sem zonas habilitadas."""


# =============================================================================
# Mapeamento de mensagens de erro
# =============================================================================

RESPONSE_MESSAGES: dict[int, str] = {
    ResponseCode.ACK: "Comando executado com sucesso",
    ResponseCode.NACK_INVALID_PACKET: "Formato de pacote inválido",
    ResponseCode.NACK_WRONG_PASSWORD: "Senha incorreta",
    ResponseCode.NACK_INVALID_COMMAND: "Comando inválido",
    ResponseCode.NACK_NOT_PARTITIONED: "Central não particionada",
    ResponseCode.NACK_ZONES_OPEN: "Zonas abertas",
    ResponseCode.NACK_DISCONTINUED: "Comando descontinuado",
    ResponseCode.NACK_NO_BYPASS_PERMISSION: "Usuário sem permissão para bypass",
    ResponseCode.NACK_NO_DEACTIVATE_PERMISSION: "Usuário sem permissão para desativar",
    ResponseCode.NACK_BYPASS_NOT_ALLOWED: "Bypass não permitido com a central ativada",
    ResponseCode.NACK_NO_ZONES_IN_PARTITION: "Partição sem zonas habilitadas",
}


def is_ack(response_code: int) -> bool:
    """Verifica se o código de resposta é ACK (sucesso).
    
    Args:
        response_code: Código de resposta recebido.
        
    Returns:
        True se for ACK, False caso contrário.
    """
    return response_code == ResponseCode.ACK


def is_nack(response_code: int) -> bool:
    """Verifica se o código de resposta é NACK (erro).
    
    Args:
        response_code: Código de resposta recebido.
        
    Returns:
        True se for NACK, False caso contrário.
    """
    return 0xE0 <= response_code <= 0xEA


def get_response_message(response_code: int) -> str:
    """Obtém a mensagem descritiva para um código de resposta.
    
    Args:
        response_code: Código de resposta recebido.
        
    Returns:
        Mensagem descritiva do código ou "Código desconhecido".
    """
    return RESPONSE_MESSAGES.get(response_code, f"Código desconhecido: 0x{response_code:02X}")


# =============================================================================
# Modelos de Centrais
# =============================================================================

class CentralModel(IntEnum):
    """Modelos de centrais de alarme Intelbras."""
    
    AMT_2018_E = 0x1E
    """AMT 2018 E/EG - Central de alarme monitorada."""
    
    AMT_4010 = 0x41
    """AMT 4010 - Central de alarme monitorada."""
    
    @classmethod
    def get_name(cls, model_code: int) -> str:
        """Retorna o nome do modelo.
        
        Args:
            model_code: Código do modelo (hex).
            
        Returns:
            Nome do modelo ou código hex se desconhecido.
        """
        model_names = {
            cls.AMT_2018_E: "AMT 2018 E/EG",
            cls.AMT_4010: "AMT 4010",
        }
        return model_names.get(model_code, f"0x{model_code:02X}")

