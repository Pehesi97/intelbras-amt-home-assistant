"""Arme/desarme Contact-ID: ISECnet R14 §§6.3/6.4 e mapa de eventos AMT."""

from dataclasses import dataclass
from datetime import datetime

from .isecnet import ISECNetFrame


@dataclass(frozen=True)
class ArmEvent:
    action: str
    code: int
    partition: int
    user_number: int | None
    occurred_at: datetime | None

    @classmethod
    def from_frame(cls, frame: ISECNetFrame) -> "ArmEvent | None":
        data = frame.content
        if len(data) != {0xB0: 16, 0xB4: 28}.get(frame.command):
            return None
        if data[0] not in (0x11, 0x12, 0x21, 0x22) or data[5:7] != b"\x01\x08" or data[7] not in (1, 3):
            return None
        # Contact-ID transmite cada dígito em um byte, com 0x0A para zero.
        if any(not 1 <= digit <= 10 for digit in data[1:16]):
            return None
        digits = "".join(str(digit % 10) for digit in data[8:16])
        code, partition, number = int(digits[:3]), int(digits[3:5]), int(digits[5:])
        if code not in (401, 403, 407, 408, 456):
            return None
        if code in (408, 456) and data[7] != 3:
            return None
        occurred_at = None
        if frame.command == 0xB4:
            try:
                day, month, year, hour, minute, second = data[16:22]
                if year > 99:
                    return None
                occurred_at = datetime(2000 + year, month, day, hour, minute, second)
            except ValueError:
                return None
        return cls(
            "Armado" if data[7] == 3 else "Desarmado", code, partition,
            number if code in (401, 456) else None, occurred_at,
        )
