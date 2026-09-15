"""Limpeza global da memória de disparos: AMT 2000/3000 R05 e 4010 R14."""

from ..checksum import CRC16
from ..isecnet import ISECNetFrame


class ClearAlarmMemoryCommand:
    """Comando interno 1C em E7; não altera a programação das zonas."""

    def build_net_frame(self) -> ISECNetFrame:
        return ISECNetFrame(command=0xE7, content=CRC16.append(b"\x01\x1c"))

    @staticmethod
    def is_response(frame: ISECNetFrame) -> bool:
        return frame.command == 0xE7 and frame.content == CRC16.append(b"\x01\x9c")

    @staticmethod
    def is_unconfirmed_response(frame: ISECNetFrame) -> bool:
        # Capturado na AMT2018 fw 8.5. Significado não documentado; nunca é ACK.
        return frame.command == 0xE7 and frame.content == b"\x00\x00"
