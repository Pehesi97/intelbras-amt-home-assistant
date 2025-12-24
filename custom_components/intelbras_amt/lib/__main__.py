"""Servidor standalone para desenvolvimento.

Execute com:
    uv run python -m custom_components.intelbras_amt.lib

Ou com opções:
    uv run python -m custom_components.intelbras_amt.lib --port 9009 --password 1234
"""

import argparse
import asyncio
import logging
import select
import sys
from datetime import datetime
from pathlib import Path

# Adiciona custom_components ao path para permitir imports
_CUSTOM_COMPONENTS_DIR = Path(__file__).parent.parent.parent.parent
if str(_CUSTOM_COMPONENTS_DIR) not in sys.path:
    sys.path.insert(0, str(_CUSTOM_COMPONENTS_DIR))

from custom_components.intelbras_amt.lib.server import AMTServer, AMTServerConfig
from custom_components.intelbras_amt.lib.protocol.isecnet import ISECNetFrame
from custom_components.intelbras_amt.lib.protocol.responses import ResponseType
from custom_components.intelbras_amt.lib.protocol.commands import (
    ActivationCommand,
    DeactivationCommand,
    PGMCommand,
    SirenCommand,
    PartialStatusRequestCommand,
    PartialCentralStatus,
    StatusRequestCommand,
    CentralStatus,
    ConnectionInfo,
    CONNECTION_INFO_COMMAND,
)
from custom_components.intelbras_amt.lib.const import DEFAULT_PORT


# Configura logging com cores
class ColoredFormatter(logging.Formatter):
    """Formatter com cores para o terminal."""
    
    COLORS = {
        'DEBUG': '\033[36m',     # Cyan
        'INFO': '\033[32m',      # Green
        'WARNING': '\033[33m',   # Yellow
        'ERROR': '\033[31m',     # Red
        'RESET': '\033[0m',
    }
    
    def format(self, record):
        color = self.COLORS.get(record.levelname, self.COLORS['RESET'])
        reset = self.COLORS['RESET']
        record.levelname = f"{color}{record.levelname}{reset}"
        return super().format(record)


def setup_logging(verbose: bool = False):
    """Configura logging."""
    level = logging.DEBUG if verbose else logging.INFO
    
    handler = logging.StreamHandler()
    handler.setFormatter(ColoredFormatter(
        '%(asctime)s │ %(levelname)s │ %(message)s',
        datefmt='%H:%M:%S'
    ))
    
    logging.basicConfig(level=level, handlers=[handler])
    
    # Reduz verbosidade de alguns loggers
    logging.getLogger('asyncio').setLevel(logging.WARNING)


def print_banner():
    """Exibe banner inicial."""
    print()
    print("\033[36m" + "═" * 60 + "\033[0m")
    print("\033[36m" + "  INTELBRAS AMT 2018 / 4010 - Servidor de Desenvolvimento" + "\033[0m")
    print("\033[36m" + "═" * 60 + "\033[0m")
    print()


async def run_server(port: int, password: str, verbose: bool):
    """Executa o servidor."""
    logger = logging.getLogger(__name__)
    
    config = AMTServerConfig(
        host="0.0.0.0",
        port=port,
        auto_ack_heartbeat=True,
    )
    
    server = AMTServer(config)
    
    # Estado
    connected_at = None
    heartbeat_count = 0
    
    @server.on_connect
    async def on_connect(conn):
        nonlocal connected_at, heartbeat_count
        connected_at = datetime.now()
        heartbeat_count = 0
        
        logger.info(f"✅ Central conectada: {conn.host}:{conn.port}")
        print()
        print("\033[32m" + "  Central conectada! Agora você pode enviar comandos." + "\033[0m")
        print("  Digite 'arm' para armar, 'disarm' para desarmar, 'help' para ajuda.")
        print()
    
    @server.on_disconnect
    async def on_disconnect(conn):
        nonlocal connected_at
        
        if connected_at:
            duration = datetime.now() - connected_at
            logger.warning(f"❌ Central desconectada após {duration}")
        else:
            logger.warning(f"❌ Central desconectada: {conn.id}")
        
        connected_at = None
    
    @server.on_frame
    async def on_frame(conn, frame: ISECNetFrame):
        # Heartbeats são tratados automaticamente, mas logamos aqui
        if frame.is_heartbeat:
            nonlocal heartbeat_count
            heartbeat_count += 1
            if verbose:
                logger.debug(f"💓 Heartbeat #{heartbeat_count}")
        elif frame.command == CONNECTION_INFO_COMMAND:
            # Comando de identificação - informações já foram logadas pelo servidor
            info = conn.metadata.get("connection_info")
            if info:
                print()
                print(f"  📋 Central identificada:")
                print(f"     Conta: {info.account}")
                print(f"     Canal: {info.channel.name_pt}")
                print(f"     MAC: ...{info.mac_suffix}")
                print()
        else:
            logger.info(f"📦 Frame recebido: cmd=0x{frame.command:02X} data={frame.content.hex()}")
    
    # Inicia servidor
    await server.start()
    
    print(f"  🔌 Servidor iniciado na porta {port}")
    print(f"  ⏳ Aguardando conexão da central...")
    print()
    print("  Configure sua central AMT para conectar em:")
    print(f"    IP: <IP desta máquina>")
    print(f"    Porta: {port}")
    print()
    print("  Comandos: arm, disarm, pgm, siren, info, info-partial, status, quit (ou Ctrl+C)")
    print()
    
    # Sinaliza quando devemos parar
    stop_event = asyncio.Event()
    
    def read_stdin_nonblocking() -> str | None:
        """Lê stdin sem bloquear, retorna None se não há input."""
        if select.select([sys.stdin], [], [], 0)[0]:
            return sys.stdin.readline()
        return None
    
    # Task para ler comandos
    async def command_loop():
        loop = asyncio.get_event_loop()
        
        while not stop_event.is_set():
            try:
                # Usa executor com função non-blocking
                line = await loop.run_in_executor(None, read_stdin_nonblocking)
                
                if line is None:
                    # Sem input, aguarda um pouco antes de verificar novamente
                    await asyncio.sleep(0.1)
                    continue
                
                line = line.strip().lower()
                
                if not line:
                    continue
                
                if line in ('quit', 'exit', 'q'):
                    logger.info("Encerrando servidor...")
                    stop_event.set()
                    return
                
                elif line == 'help':
                    print()
                    print("  Comandos disponíveis:")
                    print("    arm [a|b|c|d|stay]   - Armar alarme (todas ou partição específica)")
                    print("    disarm [a|b|c|d]     - Desarmar alarme (todas ou partição específica)")
                    print("    pgm <1-19> on|off    - Controlar PGM (ex: pgm 1 on)")
                    print("    siren on|off          - Ligar/desligar sirene (ex: siren on)")
                    print("    info                 - Solicitar status completo da central (0x5B)")
                    print("    info-partial         - Solicitar status parcial da central (0x5A)")
                    print("    status               - Ver status da conexão TCP")
                    print("    quit                 - Encerrar servidor")
                    print()
                
                elif line.startswith('arm'):
                    parts = line.split()
                    partition = parts[1] if len(parts) > 1 else None
                    
                    # Verifica conexão
                    connections = server.connections.all()
                    if not connections:
                        logger.error("❌ Nenhuma central conectada")
                        continue
                    
                    conn_id = list(connections.keys())[0]
                    
                    # Cria comando
                    if partition == 'a':
                        cmd = ActivationCommand.arm_partition_a(password)
                    elif partition == 'b':
                        cmd = ActivationCommand.arm_partition_b(password)
                    elif partition == 'c':
                        cmd = ActivationCommand.arm_partition_c(password)
                    elif partition == 'd':
                        cmd = ActivationCommand.arm_partition_d(password)
                    elif partition == 'stay':
                        cmd = ActivationCommand.arm_stay(password)
                    else:
                        cmd = ActivationCommand.arm_all(password)
                    
                    logger.info(f"📤 Enviando comando de ativação...")
                    
                    try:
                        response = await server.send_command(
                            conn_id,
                            cmd.build_net_frame(),
                            wait_response=True,
                        )
                        
                        if response.is_success:
                            logger.info("✅ Alarme armado com sucesso!")
                        else:
                            logger.error(f"❌ Erro: {response.message}")
                    
                    except TimeoutError:
                        logger.error("❌ Timeout aguardando resposta")
                    except Exception as e:
                        logger.error(f"❌ Erro: {e}")
                
                elif line.startswith('disarm'):
                    parts = line.split()
                    partition = parts[1] if len(parts) > 1 else None
                    
                    # Verifica conexão
                    connections = server.connections.all()
                    if not connections:
                        logger.error("❌ Nenhuma central conectada")
                        continue
                    
                    conn_id = list(connections.keys())[0]
                    
                    # Cria comando
                    if partition == 'a':
                        cmd = DeactivationCommand.disarm_partition_a(password)
                    elif partition == 'b':
                        cmd = DeactivationCommand.disarm_partition_b(password)
                    elif partition == 'c':
                        cmd = DeactivationCommand.disarm_partition_c(password)
                    elif partition == 'd':
                        cmd = DeactivationCommand.disarm_partition_d(password)
                    else:
                        cmd = DeactivationCommand.disarm_all(password)
                    
                    logger.info(f"📤 Enviando comando de desativação...")
                    
                    try:
                        response = await server.send_command(
                            conn_id,
                            cmd.build_net_frame(),
                            wait_response=True,
                        )
                        
                        if response.is_success:
                            logger.info("✅ Alarme desarmado com sucesso!")
                        else:
                            logger.error(f"❌ Erro: {response.message}")
                    
                    except TimeoutError:
                        logger.error("❌ Timeout aguardando resposta")
                    except Exception as e:
                        logger.error(f"❌ Erro: {e}")
                
                elif line.startswith('pgm'):
                    parts = line.split()
                    if len(parts) < 3:
                        print("  Uso: pgm <numero> on|off")
                        print("  Exemplo: pgm 1 on")
                        continue
                    
                    try:
                        pgm_num = int(parts[1])
                        action = parts[2]
                    except ValueError:
                        print("  Número de PGM inválido")
                        continue
                    
                    if pgm_num < 1 or pgm_num > 19:
                        print("  PGM deve ser entre 1 e 19")
                        continue
                    
                    if action not in ('on', 'off'):
                        print("  Ação deve ser 'on' ou 'off'")
                        continue
                    
                    # Verifica conexão
                    connections = server.connections.all()
                    if not connections:
                        logger.error("❌ Nenhuma central conectada")
                        continue
                    
                    conn_id = list(connections.keys())[0]
                    
                    # Cria comando
                    if action == 'on':
                        cmd = PGMCommand.turn_on(password, pgm_num)
                    else:
                        cmd = PGMCommand.turn_off(password, pgm_num)
                    
                    action_str = "ligar" if action == 'on' else "desligar"
                    logger.info(f"📤 Enviando comando para {action_str} PGM {pgm_num}...")
                    
                    try:
                        response = await server.send_command(
                            conn_id,
                            cmd.build_net_frame(),
                            wait_response=True,
                        )
                        
                        if response.is_success:
                            logger.info(f"✅ PGM {pgm_num} {'ligada' if action == 'on' else 'desligada'} com sucesso!")
                        else:
                            logger.error(f"❌ Erro: {response.message}")
                    
                    except TimeoutError:
                        logger.error("❌ Timeout aguardando resposta")
                    except Exception as e:
                        logger.error(f"❌ Erro: {e}")
                
                elif line.startswith('siren'):
                    parts = line.split()
                    if len(parts) < 2:
                        print("  Uso: siren on|off")
                        print("  Exemplo: siren on")
                        continue
                    
                    action = parts[1]
                    if action not in ('on', 'off'):
                        print("  Ação deve ser 'on' ou 'off'")
                        continue
                    
                    # Verifica conexão
                    connections = server.connections.all()
                    if not connections:
                        logger.error("❌ Nenhuma central conectada")
                        continue
                    
                    conn_id = list(connections.keys())[0]
                    
                    # Cria comando
                    if action == 'on':
                        cmd = SirenCommand.turn_on_siren(password)
                    else:
                        cmd = SirenCommand.turn_off_siren(password)
                    
                    action_str = "ligar" if action == 'on' else "desligar"
                    logger.info(f"📤 Enviando comando para {action_str} sirene...")
                    
                    try:
                        response = await server.send_command(
                            conn_id,
                            cmd.build_net_frame(),
                            wait_response=True,
                        )
                        
                        if response.is_success:
                            logger.info(f"✅ Sirene {'ligada' if action == 'on' else 'desligada'} com sucesso!")
                        else:
                            logger.error(f"❌ Erro: {response.message}")
                    
                    except TimeoutError:
                        logger.error("❌ Timeout aguardando resposta")
                    except Exception as e:
                        logger.error(f"❌ Erro: {e}")
                
                elif line == 'info':
                    # Verifica conexão
                    connections = server.connections.all()
                    if not connections:
                        logger.error("❌ Nenhuma central conectada")
                        continue
                    
                    conn_id = list(connections.keys())[0]
                    
                    cmd = StatusRequestCommand(password)
                    frame_to_send = cmd.build_net_frame()
                    logger.info("📤 Solicitando status da central...")
                    logger.debug(f"📤 Frame enviado: {frame_to_send.build().hex(' ')}")
                    
                    try:
                        response = await server.send_command(
                            conn_id,
                            frame_to_send,
                            wait_response=True,
                        )
                        
                        # Log detalhado da resposta
                        logger.debug(f"📥 Resposta recebida:")
                        logger.debug(f"   Tipo: {response.response_type}")
                        logger.debug(f"   Código: 0x{response.code:02X}")
                        logger.debug(f"   Tamanho dados: {len(response.data)} bytes")
                        logger.debug(f"   Dados (hex): {response.data.hex(' ') if response.data else '(vazio)'}")
                        logger.debug(f"   is_success: {response.is_success}")
                        logger.debug(f"   Mensagem: {response.message}")
                        logger.debug(f"   Frame bruto (hex): {response.raw_frame.build().hex(' ')}")
                        logger.debug(f"   Frame content: {response.raw_frame.content.hex(' ') if response.raw_frame.content else '(vazio)'}")
                        logger.debug(f"   Frame content length: {len(response.raw_frame.content)}")
                        
                        if response.is_success and response.data:
                            status = CentralStatus.try_parse(response.data)
                            if status:
                                print()
                                print("  ═══════════════════════════════════════")
                                print("  📊 STATUS DA CENTRAL")
                                print("  ═══════════════════════════════════════")
                                print()
                                
                                # Status geral
                                armed_status = "🔴 ARMADA" if status.armed else "🟢 DESARMADA"
                                print(f"  Estado: {armed_status}")
                                
                                if status.triggered:
                                    print("  ⚠️  ALARME DISPARADO!")
                                if status.siren_on:
                                    print("  🔊 Sirene LIGADA")
                                if status.has_problem:
                                    print("  ⚠️  Há problemas na central")
                                
                                print()
                                print(f"  Modelo: 0x{status.model:02X}")
                                print(f"  Firmware: v{status.firmware_version}")
                                if status.central_datetime:
                                    print(f"  Data/Hora: {status.central_datetime.strftime('%d/%m/%Y %H:%M')}")
                                
                                # Partições
                                if status.partitions.partitions_enabled:
                                    print()
                                    print("  Partições:")
                                    print(f"    A: {'🔴 Armada' if status.partitions.partition_a_armed else '🟢 Desarmada'}")
                                    print(f"    B: {'🔴 Armada' if status.partitions.partition_b_armed else '🟢 Desarmada'}")
                                    print(f"    C: {'🔴 Armada' if status.partitions.partition_c_armed else '🟢 Desarmada'}")
                                    print(f"    D: {'🔴 Armada' if status.partitions.partition_d_armed else '🟢 Desarmada'}")
                                
                                # Zonas
                                if status.zones.open_zones:
                                    print()
                                    print(f"  Zonas abertas: {sorted(status.zones.open_zones)}")
                                if status.zones.violated_zones:
                                    print(f"  Zonas violadas: {sorted(status.zones.violated_zones)}")
                                if status.zones.bypassed_zones:
                                    print(f"  Zonas em bypass: {sorted(status.zones.bypassed_zones)}")
                                
                                # PGMs
                                active_pgms = status.pgm.get_active_pgms()
                                if active_pgms:
                                    print()
                                    print(f"  PGMs ligadas: {active_pgms}")
                                
                                # Problemas
                                if status.problems.has_problems:
                                    print()
                                    print("  ⚠️  Problemas detectados:")
                                    if status.problems.ac_failure:
                                        print("    - Falta de energia elétrica")
                                    if status.problems.low_battery:
                                        print("    - Bateria baixa")
                                    if status.problems.battery_absent:
                                        print("    - Bateria ausente")
                                    if status.problems.siren_wire_cut:
                                        print("    - Fio da sirene cortado")
                                
                                print()
                                print("  ═══════════════════════════════════════")
                                print()
                            else:
                                logger.error(f"❌ Não foi possível parsear status (recebido {len(response.data)} bytes)")
                                logger.debug(f"   Dados brutos: {response.data.hex(' ')}")
                        else:
                            logger.error(f"❌ Erro: {response.message}")
                            logger.debug(f"   Tipo resposta: {response.response_type}")
                            logger.debug(f"   Código: 0x{response.code:02X}")
                            logger.debug(f"   Dados recebidos: {len(response.data)} bytes")
                            if response.data:
                                logger.debug(f"   Dados (hex): {response.data.hex(' ')}")
                            logger.debug(f"   Frame completo (hex): {response.raw_frame.build().hex(' ')}")
                            if response.raw_frame.content:
                                logger.debug(f"   Frame content (hex): {response.raw_frame.content.hex(' ')}")
                                logger.debug(f"   Frame content length: {len(response.raw_frame.content)}")
                    
                    except TimeoutError:
                        logger.error("❌ Timeout aguardando resposta")
                    except Exception as e:
                        logger.error(f"❌ Erro: {e}")
                        import traceback
                        logger.debug(f"   Traceback completo:\n{traceback.format_exc()}")
                
                elif line == 'info-partial':
                    # Verifica conexão
                    connections = server.connections.all()
                    if not connections:
                        logger.error("❌ Nenhuma central conectada")
                        continue
                    
                    conn_id = list(connections.keys())[0]
                    
                    cmd = PartialStatusRequestCommand(password)
                    frame_to_send = cmd.build_net_frame()
                    logger.info("📤 Solicitando status parcial da central (0x5A)...")
                    logger.debug(f"📤 Frame enviado: {frame_to_send.build().hex(' ')}")
                    
                    try:
                        response = await server.send_command(
                            conn_id,
                            frame_to_send,
                            wait_response=True,
                        )
                        
                        # Log detalhado da resposta
                        logger.debug(f"📥 Resposta recebida:")
                        logger.debug(f"   Tipo: {response.response_type}")
                        logger.debug(f"   Código: 0x{response.code:02X}")
                        logger.debug(f"   Tamanho dados: {len(response.data)} bytes")
                        logger.debug(f"   Dados (hex): {response.data.hex(' ') if response.data else '(vazio)'}")
                        logger.debug(f"   is_success: {response.is_success}")
                        logger.debug(f"   Mensagem: {response.message}")
                        logger.debug(f"   Frame bruto (hex): {response.raw_frame.build().hex(' ')}")
                        logger.debug(f"   Frame content: {response.raw_frame.content.hex(' ') if response.raw_frame.content else '(vazio)'}")
                        logger.debug(f"   Frame content length: {len(response.raw_frame.content)}")
                        
                        # Para status parcial, a resposta pode ser DATA com 43 bytes
                        if response.response_type == ResponseType.DATA and len(response.raw_frame.content) >= 43:
                            # Resposta com dados grandes - parseia diretamente do content
                            status = PartialCentralStatus.try_parse(response.raw_frame.content)
                            if status:
                                print()
                                print("  ═══════════════════════════════════════")
                                print("  📊 STATUS PARCIAL DA CENTRAL (0x5A)")
                                print("  ═══════════════════════════════════════")
                                print()
                                
                                # Status geral
                                armed_status = "🔴 ARMADA" if status.armed else "🟢 DESARMADA"
                                print(f"  Estado: {armed_status}")
                                
                                if status.triggered:
                                    print("  ⚠️  ALARME DISPARADO!")
                                
                                print()
                                print(f"  Modelo: 0x{status.model:02X}")
                                print(f"  Firmware: v{status.firmware_version}")
                                if status.central_datetime:
                                    print(f"  Data/Hora: {status.central_datetime.strftime('%d/%m/%Y %H:%M')}")
                                
                                # Partições
                                print()
                                print("  Partições:")
                                if status.partitions.partitions_enabled:
                                    print(f"    A: {'🔴 Armada' if status.partitions.partition_a_armed else '🟢 Desarmada'}")
                                    print(f"    B: {'🔴 Armada' if status.partitions.partition_b_armed else '🟢 Desarmada'}")
                                else:
                                    print("    Partições desabilitadas")
                                
                                # Zonas
                                print()
                                print("  Zonas:")
                                open_zones = sorted(status.zones.open_zones)
                                if open_zones:
                                    print(f"    Abertas: {open_zones}")
                                else:
                                    print("    Abertas: Nenhuma (todas fechadas)")
                                
                                violated_zones = sorted(status.zones.violated_zones)
                                if violated_zones:
                                    print(f"    Violadas: {violated_zones}")
                                else:
                                    print("    Violadas: Nenhuma")
                                
                                bypassed_zones = sorted(status.zones.bypassed_zones)
                                if bypassed_zones:
                                    print(f"    Em bypass: {bypassed_zones}")
                                else:
                                    print("    Em bypass: Nenhuma")
                                
                                # Tamper e curto-circuito
                                tamper_zones = sorted(status.zones.tamper_zones)
                                if tamper_zones:
                                    print(f"    Com tamper: {tamper_zones}")
                                
                                short_zones = sorted(status.zones.short_circuit_zones)
                                if short_zones:
                                    print(f"    Em curto-circuito: {short_zones}")
                                
                                # Bateria baixa sensores sem fio
                                low_bat_zones = sorted(status.zones.low_battery_zones)
                                if low_bat_zones:
                                    print(f"    Bateria baixa (sem fio): {low_bat_zones}")
                                
                                # Sirene e PGMs
                                print()
                                print("  Saídas:")
                                print(f"    Sirene: {'🔊 LIGADA' if status.siren_on else '🔇 Desligada'}")
                                
                                active_pgms = status.pgm.get_active_pgms()
                                if active_pgms:
                                    print(f"    PGMs ligadas: {active_pgms}")
                                else:
                                    print("    PGMs ligadas: Nenhuma")
                                
                                # Problemas
                                print()
                                if status.problems.has_problems:
                                    print("  ⚠️  Problemas detectados:")
                                    if status.problems.ac_failure:
                                        print("    - Falta de energia elétrica")
                                    if status.problems.low_battery:
                                        print("    - Bateria baixa")
                                    if status.problems.battery_absent:
                                        print("    - Bateria ausente ou invertida")
                                    if status.problems.battery_short:
                                        print("    - Bateria em curto-circuito")
                                    if status.problems.aux_overload:
                                        print("    - Sobrecarga na saída auxiliar")
                                    if status.problems.keyboard_problems:
                                        print(f"    - Problemas nos teclados: {status.problems.keyboard_problems}")
                                    if status.problems.keyboard_tamper:
                                        print(f"    - Tamper nos teclados: {status.problems.keyboard_tamper}")
                                    if status.problems.receiver_problems:
                                        print(f"    - Problemas nos receptores: {status.problems.receiver_problems}")
                                    if status.problems.siren_wire_cut:
                                        print("    - Fio da sirene cortado")
                                    if status.problems.siren_short:
                                        print("    - Curto-circuito no fio da sirene")
                                    if status.problems.phone_line_cut:
                                        print("    - Linha telefônica cortada")
                                    if status.problems.event_comm_failure:
                                        print("    - Falha ao comunicar evento")
                                else:
                                    print("  ✅ Nenhum problema detectado")
                                
                                print()
                                print("  ═══════════════════════════════════════")
                                print()
                            else:
                                logger.error(f"❌ Não foi possível parsear status parcial (recebido {len(response.raw_frame.content)} bytes)")
                        elif response.is_success and response.data:
                            # Resposta ACK com dados (formato antigo)
                            status = PartialCentralStatus.try_parse(response.data)
                            if status:
                                logger.info("✅ Status parcial recebido e parseado!")
                            else:
                                logger.error(f"❌ Não foi possível parsear status parcial (recebido {len(response.data)} bytes)")
                        else:
                            logger.error(f"❌ Erro: {response.message}")
                            logger.debug(f"   Tipo resposta: {response.response_type}")
                            logger.debug(f"   Código: 0x{response.code:02X}")
                            logger.debug(f"   Dados recebidos: {len(response.data)} bytes")
                            if response.data:
                                logger.debug(f"   Dados (hex): {response.data.hex(' ')}")
                            logger.debug(f"   Frame completo (hex): {response.raw_frame.build().hex(' ')}")
                            if response.raw_frame.content:
                                logger.debug(f"   Frame content (hex): {response.raw_frame.content.hex(' ')}")
                                logger.debug(f"   Frame content length: {len(response.raw_frame.content)}")
                    
                    except TimeoutError:
                        logger.error("❌ Timeout aguardando resposta")
                    except Exception as e:
                        logger.error(f"❌ Erro: {e}")
                        import traceback
                        logger.debug(f"   Traceback completo:\n{traceback.format_exc()}")
                
                elif line == 'status':
                    connections = server.connections.all()
                    print()
                    print(f"  Conexões ativas: {len(connections)}")
                    for conn_id, conn in connections.items():
                        print(f"    - {conn_id} (conectado em {conn.connected_at})")
                        if conn.metadata.get("account"):
                            print(f"      Conta: {conn.metadata['account']}")
                    if connected_at:
                        print(f"  Heartbeats recebidos: {heartbeat_count}")
                    print()
                
                else:
                    print(f"  Comando desconhecido: {line}")
                    print("  Digite 'help' para ver comandos disponíveis")
            
            except EOFError:
                stop_event.set()
                return
            except Exception as e:
                if not stop_event.is_set():
                    logger.error(f"Erro: {e}")
    
    # Executa
    try:
        await command_loop()
    except KeyboardInterrupt:
        logger.info("Interrompido pelo usuário")
    finally:
        await server.stop()


def main():
    """Entry point."""
    parser = argparse.ArgumentParser(
        description='Servidor Intelbras AMT 2018 / 4010 para desenvolvimento',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos:
  uv run python -m intelbras_amt
  uv run python -m intelbras_amt --port 9009 --password 1234
  uv run python -m intelbras_amt -v  # modo verbose
        """
    )
    
    parser.add_argument(
        '-p', '--port',
        type=int,
        default=DEFAULT_PORT,
        help=f'Porta TCP (padrão: {DEFAULT_PORT})'
    )
    
    parser.add_argument(
        '--password',
        type=str,
        default='1234',
        help='Senha da central (padrão: 1234)'
    )
    
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Modo verbose (mostra heartbeats e debug)'
    )
    
    args = parser.parse_args()
    
    # Valida senha
    if len(args.password) < 4 or len(args.password) > 6:
        print("Erro: Senha deve ter entre 4 e 6 dígitos")
        sys.exit(1)
    
    setup_logging(args.verbose)
    print_banner()
    
    try:
        asyncio.run(run_server(args.port, args.password, args.verbose))
    except KeyboardInterrupt:
        pass
    
    print()
    print("Servidor encerrado.")


if __name__ == "__main__":
    main()

