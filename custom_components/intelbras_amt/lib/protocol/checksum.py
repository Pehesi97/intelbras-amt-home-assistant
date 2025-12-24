"""Cálculo de checksum e CRC para protocolos ISECNet/ISECProgram.

ISECNet usa checksum XOR de 1 byte:
    - XOR de todos os bytes, depois XOR com 0xFF

ISECProgram usa CRC-16/CCITT-FALSE de 2 bytes:
    - Polinômio 0x8005, valor inicial 0x0000
"""


class Checksum:
    """Calculador de checksum para protocolo ISECNet."""

    @staticmethod
    def calculate(data: bytes | bytearray) -> int:
        """Calcula o checksum de um pacote de dados.
        
        O algoritmo faz XOR de todos os bytes e inverte o resultado
        com XOR 0xFF.
        
        Args:
            data: Bytes do pacote (sem o checksum).
            
        Returns:
            Byte de checksum calculado (0-255).
            
        Example:
            >>> Checksum.calculate(bytes([0x08, 0xE9, 0x21, 0x31, 0x32, 0x33, 0x34, 0x41, 0x21]))
            91  # 0x5B
        """
        xor = 0
        for byte in data:
            xor ^= byte
        xor ^= 0xFF
        return xor

    @staticmethod
    def verify(data: bytes | bytearray, expected_checksum: int) -> bool:
        """Verifica se o checksum de um pacote está correto.
        
        Args:
            data: Bytes do pacote (sem o checksum).
            expected_checksum: Checksum esperado.
            
        Returns:
            True se o checksum está correto, False caso contrário.
        """
        return Checksum.calculate(data) == expected_checksum

    @staticmethod
    def append(data: bytes | bytearray) -> bytes:
        """Calcula e anexa o checksum ao final dos dados.
        
        Args:
            data: Bytes do pacote (sem o checksum).
            
        Returns:
            Bytes do pacote com checksum anexado.
            
        Example:
            >>> Checksum.append(bytes([0x08, 0xE9, 0x21, 0x31, 0x32, 0x33, 0x34, 0x41, 0x21]))
            b'\\x08\\xe9!1234A!['  # Com 0x5B no final
        """
        checksum = Checksum.calculate(data)
        return bytes(data) + bytes([checksum])

    @staticmethod
    def validate_packet(packet: bytes | bytearray) -> bool:
        """Valida um pacote completo (dados + checksum).
        
        Args:
            packet: Pacote completo incluindo o byte de checksum no final.
            
        Returns:
            True se o pacote é válido, False caso contrário.
        """
        if len(packet) < 2:
            return False
        data = packet[:-1]
        checksum = packet[-1]
        return Checksum.verify(data, checksum)


class CRC16:
    """Calculador de CRC-16 para protocolo ISECProgram.
    
    Usa o algoritmo CRC-16 com polinômio 0x8005 e valor inicial 0x0000.
    """

    POLYNOMIAL = 0x8005

    @staticmethod
    def calculate(data: bytes | bytearray) -> int:
        """Calcula o CRC-16 de um buffer de dados.
        
        Args:
            data: Bytes para calcular o CRC.
            
        Returns:
            CRC-16 de 2 bytes (0-65535).
            
        Example:
            >>> CRC16.calculate(b"\\x01\\x02\\x03")
            # Retorna o CRC-16 calculado
        """
        crc = 0x0000
        
        for byte in data:
            crc ^= byte << 8
            for _ in range(8):
                if crc & 0x8000:
                    crc = (crc << 1) ^ CRC16.POLYNOMIAL
                else:
                    crc <<= 1
        
        return crc & 0xFFFF

    @staticmethod
    def calculate_bytes(data: bytes | bytearray) -> bytes:
        """Calcula o CRC-16 e retorna como 2 bytes (big-endian).
        
        Args:
            data: Bytes para calcular o CRC.
            
        Returns:
            2 bytes do CRC (big-endian).
        """
        crc = CRC16.calculate(data)
        return bytes([(crc >> 8) & 0xFF, crc & 0xFF])

    @staticmethod
    def append(data: bytes | bytearray) -> bytes:
        """Calcula e anexa o CRC-16 ao final dos dados.
        
        Args:
            data: Bytes do pacote.
            
        Returns:
            Bytes do pacote com CRC anexado.
        """
        crc_bytes = CRC16.calculate_bytes(data)
        return bytes(data) + crc_bytes

    @staticmethod
    def verify(data: bytes | bytearray, expected_crc: int) -> bool:
        """Verifica se o CRC-16 está correto.
        
        Args:
            data: Bytes do pacote (sem CRC).
            expected_crc: CRC esperado.
            
        Returns:
            True se o CRC está correto.
        """
        return CRC16.calculate(data) == expected_crc

    @staticmethod
    def validate_packet(packet: bytes | bytearray) -> bool:
        """Valida um pacote completo (dados + CRC de 2 bytes).
        
        Args:
            packet: Pacote completo incluindo os 2 bytes de CRC no final.
            
        Returns:
            True se o pacote é válido.
        """
        if len(packet) < 3:
            return False
        data = packet[:-2]
        crc = (packet[-2] << 8) | packet[-1]
        return CRC16.verify(data, crc)

