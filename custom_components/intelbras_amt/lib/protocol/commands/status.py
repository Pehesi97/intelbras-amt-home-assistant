"""Comandos de Solicitação de Status - Status da central.

- Comando 0x5A: Status parcial (43 bytes)
- Comando 0x5B: Status completo (54 bytes)

Estrutura dos comandos:
    - Código: 0x5A ou 0x5B
    - Conteúdo: Nenhum (comando simples)

Exemplos da documentação:
    Status parcial (0x5A):
        Requisição: 08 E9 21 31 32 33 34 5A 21 40
        Resposta: 2C E9 <43 bytes de status> XX (checksum)
    
    Status completo (0x5B):
        Requisição: 08 E9 21 31 32 33 34 5B 21 41
        Resposta: 37 E9 <54 bytes de status> XX (checksum)
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Self

from ...const import CommandCode
from .base import Command


class PartialStatusRequestCommand(Command):
    """Comando para solicitar status parcial da central (43 bytes).
    
    Este comando não tem conteúdo, apenas solicita o status parcial.
    A resposta deve ser parseada com PartialCentralStatus.parse().
    """

    def __init__(self, password: str) -> None:
        """Inicializa o comando de solicitação de status parcial.
        
        Args:
            password: Senha do usuário (4-6 dígitos).
        """
        super().__init__(password)

    @property
    def code(self) -> int:
        """Código do comando de status parcial (0x5A)."""
        return CommandCode.STATUS_REQUEST_PARTIAL

    def build_content(self) -> bytes:
        """Comando não tem conteúdo."""
        return bytes()

    def __repr__(self) -> str:
        return "PartialStatusRequestCommand(password='****')"


class StatusRequestCommand(Command):
    """Comando para solicitar status completo da central.
    
    Este comando não tem conteúdo, apenas solicita o status.
    A resposta deve ser parseada com CentralStatus.parse().
    """

    def __init__(self, password: str) -> None:
        """Inicializa o comando de solicitação de status.
        
        Args:
            password: Senha do usuário (4-6 dígitos).
        """
        super().__init__(password)

    @property
    def code(self) -> int:
        """Código do comando de status (0x5B)."""
        return CommandCode.STATUS_REQUEST

    def build_content(self) -> bytes:
        """Comando não tem conteúdo."""
        return bytes()

    def __repr__(self) -> str:
        return "StatusRequestCommand(password='****')"


@dataclass
class ZoneStatus:
    """Status das zonas da central (até 64 zonas)."""
    
    open_zones: set[int] = field(default_factory=set)
    """Zonas abertas (1-64)."""
    
    violated_zones: set[int] = field(default_factory=set)
    """Zonas violadas/disparadas (1-64)."""
    
    bypassed_zones: set[int] = field(default_factory=set)
    """Zonas anuladas/em bypass (1-64)."""
    
    tamper_zones: set[int] = field(default_factory=set)
    """Zonas com tamper (1-8)."""
    
    short_circuit_zones: set[int] = field(default_factory=set)
    """Zonas em curto-circuito (1-8)."""
    
    low_battery_zones: set[int] = field(default_factory=set)
    """Zonas com bateria baixa em sensor sem fio (17-64)."""

    @staticmethod
    def _parse_bitmask(data: bytes, start_zone: int = 1) -> set[int]:
        """Parseia bitmask de zonas.
        
        Args:
            data: Bytes do bitmask (cada byte = 8 zonas).
            start_zone: Número da primeira zona.
            
        Returns:
            Set com números das zonas ativas.
        """
        zones = set()
        for byte_idx, byte_val in enumerate(data):
            for bit_idx in range(8):
                if byte_val & (1 << bit_idx):
                    zone_num = start_zone + (byte_idx * 8) + bit_idx
                    zones.add(zone_num)
        return zones


@dataclass
class PartitionStatus:
    """Status das partições."""
    
    partitions_enabled: bool = False
    """Se a central está configurada com partições."""
    
    partition_a_armed: bool = False
    """Partição A está armada."""
    
    partition_b_armed: bool = False
    """Partição B está armada."""
    
    partition_c_armed: bool = False
    """Partição C está armada."""
    
    partition_d_armed: bool = False
    """Partição D está armada."""
    
    @property
    def any_armed(self) -> bool:
        """Verifica se alguma partição está armada."""
        return any([
            self.partition_a_armed,
            self.partition_b_armed,
            self.partition_c_armed,
            self.partition_d_armed,
        ])
    
    @property
    def all_armed(self) -> bool:
        """Verifica se todas as partições estão armadas."""
        return all([
            self.partition_a_armed,
            self.partition_b_armed,
            self.partition_c_armed,
            self.partition_d_armed,
        ])


@dataclass
class PGMStatus:
    """Status das saídas PGM (1-19)."""
    
    pgm_states: dict[int, bool] = field(default_factory=dict)
    """Estado de cada PGM (True = ligada, False = desligada)."""
    
    def is_on(self, pgm_number: int) -> bool:
        """Verifica se uma PGM está ligada."""
        return self.pgm_states.get(pgm_number, False)
    
    def get_active_pgms(self) -> list[int]:
        """Retorna lista de PGMs ligadas."""
        return [num for num, state in self.pgm_states.items() if state]


@dataclass  
class SystemProblems:
    """Problemas detectados na central."""
    
    # Energia
    ac_failure: bool = False
    """Falta de rede elétrica."""
    
    low_battery: bool = False
    """Bateria baixa."""
    
    battery_absent: bool = False
    """Bateria ausente ou invertida."""
    
    battery_short: bool = False
    """Bateria em curto-circuito."""
    
    aux_overload: bool = False
    """Sobrecarga na saída auxiliar."""
    
    # Teclados
    keyboard_problems: list[int] = field(default_factory=list)
    """Teclados com problema (1-4)."""
    
    keyboard_tamper: list[int] = field(default_factory=list)
    """Teclados com tamper (1-4)."""
    
    # Receptores
    receiver_problems: list[int] = field(default_factory=list)
    """Receptores com problema (1-4)."""
    
    # Expansores
    pgm_expander_problems: list[int] = field(default_factory=list)
    """Expansores de PGM com problema (1-4)."""
    
    zone_expander_problems: list[int] = field(default_factory=list)
    """Expansores de zonas com problema (1-6)."""
    
    # Sirene
    siren_wire_cut: bool = False
    """Corte do fio da sirene."""
    
    siren_short: bool = False
    """Curto-circuito no fio da sirene."""
    
    phone_line_cut: bool = False
    """Corte de linha telefônica."""
    
    event_comm_failure: bool = False
    """Falha ao comunicar evento."""
    
    @property
    def has_problems(self) -> bool:
        """Verifica se há algum problema."""
        return any([
            self.ac_failure,
            self.low_battery,
            self.battery_absent,
            self.battery_short,
            self.aux_overload,
            len(self.keyboard_problems) > 0,
            len(self.keyboard_tamper) > 0,
            len(self.receiver_problems) > 0,
            len(self.pgm_expander_problems) > 0,
            len(self.zone_expander_problems) > 0,
            self.siren_wire_cut,
            self.siren_short,
            self.phone_line_cut,
            self.event_comm_failure,
        ])


@dataclass
class CentralStatus:
    """Status completo da central de alarme.
    
    Parseado a partir da resposta de 54 bytes do comando 0x5B.
    """
    
    # Informações gerais
    model: int = 0
    """Modelo da central (0x41 = AMT4010)."""
    
    firmware_version: str = ""
    """Versão do firmware (ex: "3.1")."""
    
    # Status de funcionamento
    armed: bool = False
    """Central está armada."""
    
    triggered: bool = False
    """Alguma zona está disparada."""
    
    siren_on: bool = False
    """Sirene está ligada."""
    
    has_problem: bool = False
    """Há problema na central."""
    
    # Data/hora da central
    central_datetime: datetime | None = None
    """Data e hora da central."""
    
    # Sub-status
    zones: ZoneStatus = field(default_factory=ZoneStatus)
    """Status das zonas."""
    
    partitions: PartitionStatus = field(default_factory=PartitionStatus)
    """Status das partições."""
    
    pgm: PGMStatus = field(default_factory=PGMStatus)
    """Status das PGMs."""
    
    problems: SystemProblems = field(default_factory=SystemProblems)
    """Problemas do sistema."""
    
    # Dados brutos
    raw_data: bytes = field(default_factory=bytes)
    """54 bytes brutos da resposta."""

    @classmethod
    def parse(cls, data: bytes | bytearray) -> Self:
        """Parseia os 54 bytes de status da central.
        
        Args:
            data: 54 bytes de status recebidos.
            
        Returns:
            Instância de CentralStatus com todos os campos parseados.
            
        Raises:
            ValueError: Se os dados não tiverem 54 bytes.
        """
        if len(data) != 54:
            raise ValueError(f"Status deve ter 54 bytes, recebido {len(data)}")
        
        status = cls(raw_data=bytes(data))
        
        # === Zonas abertas (Status01-08, bytes 0-7) ===
        status.zones.open_zones = ZoneStatus._parse_bitmask(data[0:8], start_zone=1)
        
        # === Zonas violadas (Status09-16, bytes 8-15) ===
        status.zones.violated_zones = ZoneStatus._parse_bitmask(data[8:16], start_zone=1)
        
        # === Zonas anuladas/bypass (Status17-24, bytes 16-23) ===
        status.zones.bypassed_zones = ZoneStatus._parse_bitmask(data[16:24], start_zone=1)
        
        # === Modelo (Status25, byte 24) ===
        status.model = data[24]
        
        # === Versão firmware (Status26, byte 25) ===
        # Cada nibble é um dígito (0x31 = versão 3.1)
        high_nibble = (data[25] >> 4) & 0x0F
        low_nibble = data[25] & 0x0F
        status.firmware_version = f"{high_nibble}.{low_nibble}"
        
        # === Partição habilitada (Status27, byte 26) ===
        status.partitions.partitions_enabled = data[26] == 0x01
        
        # === Partições A e B (Status28, byte 27) ===
        status.partitions.partition_a_armed = bool(data[27] & 0x01)
        status.partitions.partition_b_armed = bool(data[27] & 0x02)
        
        # === Partições C e D (Status29, byte 28) ===
        status.partitions.partition_c_armed = bool(data[28] & 0x01)
        status.partitions.partition_d_armed = bool(data[28] & 0x02)
        
        # === Funcionamento (Status30, byte 29) ===
        func_byte = data[29]
        status.armed = bool(func_byte & 0x08)
        status.triggered = bool(func_byte & 0x04) or bool(func_byte & 0x44)
        status.siren_on = bool(func_byte & 0x02)
        status.has_problem = bool(func_byte & 0x11)
        
        # === Data/Hora (Status31-35, bytes 30-34) ===
        # IMPORTANTE: A central AMT usa HEXADECIMAL PURO, não BCD!
        # Status31: Hora em HEX (0x12 = 18h decimal)
        # Status32: Minuto em HEX (0x3b = 59min decimal)
        # Status33: Dia em HEX (0x12 = 18 decimal)
        # Status34: Mês em HEX (0x0c = 12 decimal = dezembro)
        # Status35: Ano em HEX (0x19 = 25 decimal = 2025)
        try:
            hour = data[30]      # HEX direto (0-23)
            minute = data[31]    # HEX direto (0-59)
            day = data[32]       # HEX direto (1-31)
            month = data[33]     # HEX direto (1-12)
            year = 2000 + data[34]  # HEX direto + 2000
            
            status.central_datetime = datetime(year, month, day, hour, minute)
        except ValueError:
            status.central_datetime = None
        
        # === Problemas de energia (Status36, byte 35) ===
        status.problems.ac_failure = bool(data[35] & 0x01)
        status.problems.low_battery = bool(data[35] & 0x02)
        status.problems.battery_absent = bool(data[35] & 0x04)
        status.problems.battery_short = bool(data[35] & 0x08)
        status.problems.aux_overload = bool(data[35] & 0x10)
        
        # === Problemas teclados/receptores (Status37, byte 36) ===
        for i in range(4):
            if data[36] & (1 << i):
                status.problems.keyboard_problems.append(i + 1)
            if data[36] & (1 << (i + 4)):
                status.problems.receiver_problems.append(i + 1)
        
        # === Problemas expansores (Status38, byte 37) ===
        for i in range(4):
            if data[37] & (1 << i):
                status.problems.pgm_expander_problems.append(i + 1)
        for i in range(4):
            if data[37] & (1 << (i + 4)):
                status.problems.zone_expander_problems.append(i + 1)
        
        # === Mais expansores de zonas (Status39, byte 38) ===
        if data[38] & 0x01:
            status.problems.zone_expander_problems.append(5)
        if data[38] & 0x02:
            status.problems.zone_expander_problems.append(6)
        
        # === Tamper teclados (Status42, byte 41) ===
        for i in range(4):
            if data[41] & (1 << (i + 4)):
                status.problems.keyboard_tamper.append(i + 1)
        
        # === Problemas sirene/telefone (Status43, byte 42) ===
        status.problems.siren_wire_cut = bool(data[42] & 0x01)
        status.problems.siren_short = bool(data[42] & 0x02)
        status.problems.phone_line_cut = bool(data[42] & 0x04)
        status.problems.event_comm_failure = bool(data[42] & 0x08)
        
        # === Tamper zonas (Status44, byte 43) ===
        status.zones.tamper_zones = ZoneStatus._parse_bitmask(data[43:44], start_zone=1)
        
        # === Curto-circuito zonas (Status45, byte 44) ===
        status.zones.short_circuit_zones = ZoneStatus._parse_bitmask(data[44:45], start_zone=1)
        
        # === Status sirene e PGMs 1-3 (Status46, byte 45) ===
        # Bit 2: Sirene (já tratado em siren_on)
        status.pgm.pgm_states[1] = bool(data[45] & 0x40)  # Bit 6
        status.pgm.pgm_states[2] = bool(data[45] & 0x20)  # Bit 5
        status.pgm.pgm_states[3] = bool(data[45] & 0x10)  # Bit 4
        
        # === Bateria baixa sensores sem fio (Status47-52, bytes 46-51) ===
        # Zonas 17-64
        low_bat_data = data[46:52]
        for byte_idx, byte_val in enumerate(low_bat_data):
            for bit_idx in range(8):
                if byte_val & (1 << bit_idx):
                    zone_num = 17 + (byte_idx * 8) + bit_idx
                    status.zones.low_battery_zones.add(zone_num)
        
        # === Estado PGMs 4-11 (Status53, byte 52) ===
        for i in range(8):
            status.pgm.pgm_states[4 + i] = bool(data[52] & (1 << i))
        
        # === Estado PGMs 12-19 (Status54, byte 53) ===
        for i in range(8):
            status.pgm.pgm_states[12 + i] = bool(data[53] & (1 << i))
        
        return status

    @classmethod
    def try_parse(cls, data: bytes | bytearray) -> Self | None:
        """Tenta parsear os dados, retorna None se falhar."""
        try:
            return cls.parse(data)
        except (ValueError, IndexError):
            return None

    def __repr__(self) -> str:
        armed_str = "ARMADA" if self.armed else "DESARMADA"
        return (
            f"CentralStatus({armed_str}, "
            f"triggered={self.triggered}, "
            f"siren={self.siren_on}, "
            f"problems={self.problems.has_problems})"
        )


@dataclass
class PartialCentralStatus:
    """Status parcial da central de alarme (43 bytes).
    
    Parseado a partir da resposta de 43 bytes do comando 0x5A.
    Similar ao CentralStatus, mas com menos campos.
    """
    
    # Informações gerais
    model: int = 0
    """Modelo da central (0x1E = AMT 2018 E/EG, 0x41 = AMT 4010)."""
    
    firmware_version: str = ""
    """Versão do firmware (ex: "3.1")."""
    
    # Status de funcionamento
    armed: bool = False
    """Central está armada."""
    
    triggered: bool = False
    """Alguma zona está disparada."""
    
    siren_on: bool = False
    """Sirene está ligada."""
    
    has_problem: bool = False
    """Há problema na central."""
    
    # Data/hora da central
    central_datetime: datetime | None = None
    """Data e hora da central."""
    
    # Sub-status
    zones: ZoneStatus = field(default_factory=ZoneStatus)
    """Status das zonas (até 48 zonas para status parcial)."""
    
    partitions: PartitionStatus = field(default_factory=PartitionStatus)
    """Status das partições (apenas A e B no parcial)."""
    
    pgm: PGMStatus = field(default_factory=PGMStatus)
    """Status das PGMs (apenas 1 e 2 no parcial)."""
    
    problems: SystemProblems = field(default_factory=SystemProblems)
    """Problemas do sistema."""
    
    # Dados brutos
    raw_data: bytes = field(default_factory=bytes)
    """43 bytes brutos da resposta."""

    @classmethod
    def parse(cls, data: bytes | bytearray) -> Self:
        """Parseia os 43 bytes de status parcial da central.
        
        Args:
            data: 43 bytes de status recebidos.
            
        Returns:
            Instância de PartialCentralStatus com todos os campos parseados.
            
        Raises:
            ValueError: Se os dados não tiverem 43 bytes.
        """
        if len(data) != 43:
            raise ValueError(f"Status parcial deve ter 43 bytes, recebido {len(data)}")
        
        status = cls(raw_data=bytes(data))
        
        # === Zonas abertas (Status01-06, bytes 0-5) ===
        # Zonas 1-48
        status.zones.open_zones = ZoneStatus._parse_bitmask(data[0:6], start_zone=1)
        
        # === Zonas violadas (Status07-12, bytes 6-11) ===
        # Zonas 1-48
        status.zones.violated_zones = ZoneStatus._parse_bitmask(data[6:12], start_zone=1)
        
        # === Zonas anuladas/bypass (Status13-18, bytes 12-17) ===
        # Zonas 1-32
        status.zones.bypassed_zones = ZoneStatus._parse_bitmask(data[12:18], start_zone=1)
        
        # === Modelo (Status19, byte 18) ===
        status.model = data[18]
        
        # === Versão firmware (Status20, byte 19) ===
        high_nibble = (data[19] >> 4) & 0x0F
        low_nibble = data[19] & 0x0F
        status.firmware_version = f"{high_nibble}.{low_nibble}"
        
        # === Partição habilitada (Status21, byte 20) ===
        status.partitions.partitions_enabled = data[20] == 0x01
        
        # === Partições A e B (Status22, byte 21) ===
        status.partitions.partition_a_armed = bool(data[21] & 0x01)
        status.partitions.partition_b_armed = bool(data[21] & 0x02)
        # Status parcial não inclui partições C e D
        
        # === Funcionamento (Status23, byte 22) ===
        func_byte = data[22]
        status.armed = bool(func_byte & 0x08)
        status.triggered = bool(func_byte & 0x04) or bool(func_byte & 0x44)
        status.siren_on = bool(func_byte & 0x02)
        status.has_problem = bool(func_byte & 0x11)
        
        # === Data/Hora (Status24-28, bytes 23-27) ===
        # IMPORTANTE: A central AMT usa HEXADECIMAL PURO, não BCD!
        # Status24: Hora em HEX (0x12 = 18h decimal)
        # Status25: Minuto em HEX (0x3b = 59min decimal)
        # Status26: Dia em HEX (0x12 = 18 decimal)
        # Status27: Mês em HEX (0x0c = 12 decimal = dezembro)
        # Status28: Ano em HEX (0x19 = 25 decimal = 2025)
        try:
            hour = data[23]      # HEX direto (0-23)
            minute = data[24]    # HEX direto (0-59)
            day = data[25]       # HEX direto (1-31)
            month = data[26]     # HEX direto (1-12)
            year = 2000 + data[27]  # HEX direto + 2000
            
            status.central_datetime = datetime(year, month, day, hour, minute)
        except ValueError:
            status.central_datetime = None
        
        # === Problemas de energia (Status29, byte 28) ===
        status.problems.ac_failure = bool(data[28] & 0x01)
        status.problems.low_battery = bool(data[28] & 0x02)
        status.problems.battery_absent = bool(data[28] & 0x04)
        status.problems.battery_short = bool(data[28] & 0x08)
        status.problems.aux_overload = bool(data[28] & 0x10)
        
        # === Problemas teclados/receptores (Status30, byte 29) ===
        for i in range(4):
            if data[29] & (1 << i):
                status.problems.keyboard_problems.append(i + 1)
            if data[29] & (1 << (i + 4)):
                status.problems.receiver_problems.append(i + 1)
        
        # === Nível bateria (Status31, byte 30) ===
        # Informações sobre nível da bateria (não parseamos em detalhes por enquanto)
        
        # === Tamper teclados (Status32, byte 31) ===
        for i in range(4):
            if data[31] & (1 << (i + 4)):
                status.problems.keyboard_tamper.append(i + 1)
        
        # === Problemas sirene/telefone (Status33, byte 32) ===
        status.problems.siren_wire_cut = bool(data[32] & 0x01)
        status.problems.siren_short = bool(data[32] & 0x02)
        status.problems.phone_line_cut = bool(data[32] & 0x04)
        status.problems.event_comm_failure = bool(data[32] & 0x08)
        
        # === Tamper zonas (Status34-35, bytes 33-34) ===
        # Zonas 1-18
        tamper_data = data[33:35]
        for byte_idx, byte_val in enumerate(tamper_data):
            for bit_idx in range(8):
                if byte_val & (1 << bit_idx):
                    zone_num = 1 + (byte_idx * 8) + bit_idx
                    if zone_num <= 18:
                        status.zones.tamper_zones.add(zone_num)
        
        # === Curto-circuito zonas (Status36-37, bytes 35-36) ===
        # Zonas 1-18
        short_data = data[35:37]
        for byte_idx, byte_val in enumerate(short_data):
            for bit_idx in range(8):
                if byte_val & (1 << bit_idx):
                    zone_num = 1 + (byte_idx * 8) + bit_idx
                    if zone_num <= 18:
                        status.zones.short_circuit_zones.add(zone_num)
        
        # === Status sirene e PGMs 1-2 (Status38, byte 37) ===
        # Status38 tem informação mais específica sobre sirene e PGMs
        # Bit 2: Status sirene (sobrescreve Status23 se disponível)
        if data[37] & 0x04:  # Se bit 2 está setado, sirene está ligada
            status.siren_on = True
        # Caso contrário, mantém o valor do Status23
        
        status.pgm.pgm_states[1] = bool(data[37] & 0x40)  # Bit 6
        status.pgm.pgm_states[2] = bool(data[37] & 0x20)  # Bit 5
        
        # === Bateria baixa sensores sem fio (Status39-43, bytes 38-42) ===
        # Zonas 1-40
        low_bat_data = data[38:43]
        for byte_idx, byte_val in enumerate(low_bat_data):
            for bit_idx in range(8):
                if byte_val & (1 << bit_idx):
                    zone_num = 1 + (byte_idx * 8) + bit_idx
                    if zone_num <= 40:
                        status.zones.low_battery_zones.add(zone_num)
        
        return status

    @classmethod
    def try_parse(cls, data: bytes | bytearray) -> Self | None:
        """Tenta parsear os dados, retorna None se falhar."""
        try:
            return cls.parse(data)
        except (ValueError, IndexError):
            return None

    def __repr__(self) -> str:
        armed_str = "ARMADA" if self.armed else "DESARMADA"
        return (
            f"PartialCentralStatus({armed_str}, "
            f"triggered={self.triggered}, "
            f"siren={self.siren_on}, "
            f"problems={self.problems.has_problems})"
        )

