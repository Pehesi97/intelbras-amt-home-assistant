"""Short, authenticated local programming sessions (beta)."""

import asyncio
import logging
import sys

from ..const import CentralModel
from .checksum import CRC16
from .isecnet import ISECNetFrame, ISECNetFrameReader
from .commands.clear_alarm import ClearAlarmMemoryCommand

_LOGGER = logging.getLogger(__name__)

# Model-specific status size (including CRC) and zone bitmap groups.
PROGRAMMING_MODELS = {
    CentralModel.AMT_2018_E: (29, 6),
    CentralModel.AMT_2018_E_SMART: (29, 6),
    CentralModel.AMT_1000_SMART: (29, 6),
    CentralModel.AMT_4010: (35, 8),
}


def identify_frame(password: str) -> ISECNetFrame:
    if not (isinstance(password, str) and len(password) == 6 and password.isascii() and password.isdigit()):
        raise ValueError("A senha do computador deve ter 6 dígitos")
    # AMT Remoto Mobile capture: zero is nibble A; software version byte is 34.
    encoded = bytes.fromhex(password.replace("0", "a"))
    return ISECNetFrame(0xE7, CRC16.append(b"\x05\x11" + encoded + b"\x34"))


def command_frame(code: int, data: bytes = b"") -> ISECNetFrame:
    return ISECNetFrame(0xE7, CRC16.append(bytes((1 + len(data), code)) + data))


def parse_status(content: bytes) -> dict:
    if (len(content) < 5 or content[1] != 0x97 or content[0] + 3 != len(content)
            or not CRC16.validate_packet(content)):
        raise ValueError("Resposta de status de programação inválida")
    layout = PROGRAMMING_MODELS.get(content[2])
    if layout is None:
        raise ValueError("Modelo sem suporte à limpeza de disparos nesta beta")
    length, groups = layout
    if len(content) != length:
        raise ValueError("Formato de status de programação incompatível com o modelo")
    return {
        "model": content[2],
        "partitions": content[4],
        "violated": {group * 8 + bit + 1 for group in range(groups) for bit in range(8)
                     if content[6 + 2 * group] & (1 << bit)},
    }


class ProgrammingSession:
    """One session per operation; never log credential frames or programming data."""

    def __init__(self, host: str, password: str, port: int = 9009):
        self._host = host
        self._port = port
        self._auth_frame = identify_frame(password)
        self._reader = self._writer = None
        self._frames = ISECNetFrameReader()
        self._authenticated = False

    async def __aenter__(self):
        try:
            self._reader, self._writer = await asyncio.wait_for(
                asyncio.open_connection(self._host, self._port), 8,
            )
            await self._request(command_frame(0x10), {0x90})
            await asyncio.sleep(0.3)  # Match the observed app handshake.
            reply = await self._request(self._auth_frame, {0x50, 0x53, 0x56, 0x43})
            self._authenticated = reply == CRC16.append(b"\x01\x50")
            if not self._authenticated:
                if reply == CRC16.append(b"\x01\x53"):
                    raise PermissionError("A central rejeitou a senha do computador")
                raise ValueError("A central não aceitou a sessão de programação")
            await asyncio.sleep(0.4)
            return self
        except BaseException:
            await self.__aexit__(*sys.exc_info())
            raise

    async def __aexit__(self, exc_type, exc, traceback):
        logout_error = None
        try:
            if self._authenticated:
                try:
                    await self._request(command_frame(0x15), {0x95})
                except (OSError, ValueError) as err:
                    logout_error = err
                    _LOGGER.warning("A central não confirmou o encerramento da sessão de programação")
        finally:
            self._authenticated = False
            if self._writer is not None:
                self._writer.close()
                try:
                    await asyncio.wait_for(self._writer.wait_closed(), 2)
                except (OSError, TimeoutError):
                    pass
        if logout_error and exc_type is None:
            raise OSError("Encerramento da sessão de programação não confirmado") from logout_error

    async def _request(self, frame: ISECNetFrame, expected: set[int]) -> bytes:
        async with asyncio.timeout(8):
            self._writer.write(frame.build())
            await self._writer.drain()
            while data := await self._reader.read(4096):
                for response in self._frames.feed(data):
                    content = response.content
                    if response.command != 0xE7:
                        continue
                    if content == b"\x00\x00":
                        raise ValueError("A central não confirmou a operação de programação")
                    if (len(content) >= 4 and content[0] + 3 == len(content)
                            and CRC16.validate_packet(content) and content[1] in expected):
                        return content
            raise ConnectionError("Conexão de programação encerrada pela central")

    async def read_status(self) -> dict:
        return parse_status(await self._request(command_frame(0x17), {0x97}))

    async def clear_alarm_memory(self) -> None:
        status = await self.read_status()
        functions = await self._request(command_frame(0x19, b"\x10"), {0x99})
        if len(functions) != 5 or functions[:2] != b"\x02\x99":
            raise ValueError("Resposta de status da sirene inválida")
        if status["partitions"] != 0 or functions[2] & 4:
            raise ValueError("Limpeza exige todas as partições desarmadas e sirene desligada")
        if not status["violated"]:
            return
        # Exactly one attempt; neither failed acknowledgement nor readback causes a retry.
        reply = await self._request(ClearAlarmMemoryCommand().build_net_frame(), {0x9C})
        if reply != CRC16.append(b"\x01\x9c"):
            raise ValueError("A central não confirmou a limpeza")
        if (await self.read_status())["violated"]:
            raise ValueError("A central confirmou o comando, mas ainda há zonas na memória de disparos")
