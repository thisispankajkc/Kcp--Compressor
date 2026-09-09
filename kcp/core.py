import struct

class BitStreamWriter:
    def __init__(self):
        self.bytes = bytearray()
        self.buffer = 0
        self.bits_in_buffer = 0

    def write_bit(self, bit: int):
        self.buffer = (self.buffer << 1) | (bit & 1)
        self.bits_in_buffer += 1
        if self.bits_in_buffer == 8:
            self.bytes.append(self.buffer)
            self.buffer = 0
            self.bits_in_buffer = 0

    def flush(self):
        if self.bits_in_buffer > 0:
            self.bytes.append(self.buffer << (8 - self.bits_in_buffer))
            self.buffer = 0
            self.bits_in_buffer = 0
        return bytes(self.bytes)


class BitStreamReader:
    def __init__(self, data: bytes):
        self.data = data
        self.byte_idx = 0
        self.bit_idx = 7

    def read_bit(self) -> int:
        if self.byte_idx >= len(self.data):
            return 0
        bit = (self.data[self.byte_idx] >> self.bit_idx) & 1
        self.bit_idx -= 1
        if self.bit_idx < 0:
            self.bit_idx = 7
            self.byte_idx += 1
        return bit


def delta_transform(data: bytes) -> bytes:
    out = bytearray(len(data))
    prev = 0
    for i in range(len(data)):
        out[i] = data[i] ^ prev
        prev = data[i]
    return bytes(out)


def inverse_delta_transform(data: bytes) -> bytes:
    out = bytearray(len(data))
    prev = 0
    for i in range(len(data)):
        out[i] = data[i] ^ prev
        prev = out[i]
    return bytes(out)


class ArithmeticOrder2Coder:
    MAX_RANGE = 0xFFFFFFFF
    HALF = 0x80000000
    QTR  = 0x40000000

    def compress_block(self, block: bytes) -> bytes:
        writer = BitStreamWriter()
        low = 0
        high = self.MAX_RANGE
        pending_bits = 0
        
        context_table = [[1, 1] for _ in range(65536)]
        context = 0

        for byte in block:
            for bit_pos in range(7, -1, -1):
                bit = (byte >> bit_pos) & 1
                
                c_zero, c_one = context_table[context]
                total = c_zero + c_one
                
                range_size = high - low + 1
                split = low + (range_size * c_zero) // total
                
                if bit == 0:
                    high = split - 1
                    if c_zero + c_one > 254:
                        context_table[context][0] = (c_zero >> 1) + 1
                        context_table[context][1] = (c_one >> 1) + 1
                    context_table[context][0] += 1
                else:
                    low = split
                    if c_zero + c_one > 254:
                        context_table[context][0] = (c_zero >> 1) + 1
                        context_table[context][1] = (c_one >> 1) + 1
                    context_table[context][1] += 1
                
                context = ((context << 1) | bit) & 0xFFFF
                
                while True:
                    if high < self.HALF:
                        writer.write_bit(0)
                        for _ in range(pending_bits): writer.write_bit(1)
                        pending_bits = 0
                    elif low >= self.HALF:
                        writer.write_bit(1)
                        for _ in range(pending_bits): writer.write_bit(0)
                        pending_bits = 0
                        low -= self.HALF
                        high -= self.HALF
                    elif low >= self.QTR and high < 3 * self.QTR:
                        pending_bits += 1
                        low -= self.QTR
                        high -= self.QTR
                    else:
                        break
                    low = (low << 1) & self.MAX_RANGE
                    high = ((high << 1) | 1) & self.MAX_RANGE

        pending_bits += 1
        if low < self.QTR:
            writer.write_bit(0)
            for _ in range(pending_bits): writer.write_bit(1)
        else:
            writer.write_bit(1)
            for _ in range(pending_bits): writer.write_bit(0)

        return writer.flush()

    def decompress_block(self, compressed_data: bytes, block_size: int) -> bytes:
        reader = BitStreamReader(compressed_data)
        low = 0
        high = self.MAX_RANGE
        value = 0

        for _ in range(32):
            value = (value << 1) | reader.read_bit()

        context_table = [[1, 1] for _ in range(65536)]
        context = 0
        decompressed = bytearray()

        for _ in range(block_size):
            byte_val = 0
            for bit_pos in range(7, -1, -1):
                c_zero, c_one = context_table[context]
                total = c_zero + c_one
                
                range_size = high - low + 1
                split = low + (range_size * c_zero) // total
                
                if value <= split - 1:
                    bit = 0
                    high = split - 1
                    if c_zero + c_one > 254:
                        context_table[context][0] = (c_zero >> 1) + 1
                        context_table[context][1] = (c_one >> 1) + 1
                    context_table[context][0] += 1
                else:
                    bit = 1
                    low = split
                    if c_zero + c_one > 254:
                        context_table[context][0] = (c_zero >> 1) + 1
                        context_table[context][1] = (c_one >> 1) + 1
                    context_table[context][1] += 1

                byte_val |= (bit << bit_pos)
                context = ((context << 1) | bit) & 0xFFFF

                while True:
                    if high < self.HALF:
                        pass
                    elif low >= self.HALF:
                        low -= self.HALF
                        high -= self.HALF
                        value -= self.HALF
                    elif low >= self.QTR and high < 3 * self.QTR:
                        low -= self.QTR
                        high -= self.QTR
                        value -= self.QTR
                    else:
                        break
                    low = (low << 1) & self.MAX_RANGE
                    high = ((high << 1) | 1) & self.MAX_RANGE
                    value = ((value << 1) | reader.read_bit()) & self.MAX_RANGE

            decompressed.append(byte_val)

        return bytes(decompressed)


def compress_to_kcp(input_data: bytes, block_size: int = 8192) -> bytes:
    coder = ArithmeticOrder2Coder()
    output_payload = bytearray()
    
    header = struct.pack('<4sI', b'KCP4', len(input_data))
    output_payload.extend(header)

    for i in range(0, len(input_data), block_size):
        block = input_data[i : i + block_size]
        
        enc_direct = coder.compress_block(block)
        delta_block = delta_transform(block)
        enc_delta = coder.compress_block(delta_block)

        candidates = [
            (0x00, block),
            (0x01, enc_direct),
            (0x02, enc_delta)
        ]
        
        best_mode, best_payload = min(candidates, key=lambda x: len(x[1]))

        if best_mode == 0x00:
            output_payload.append(0x00)
            output_payload.extend(struct.pack('>H', len(block)))
            output_payload.extend(block)
        else:
            output_payload.append(best_mode)
            output_payload.extend(struct.pack('>HH', len(best_payload), len(block)))
            output_payload.extend(best_payload)

    return bytes(output_payload)


def decompress_from_kcp(kcp_data: bytes) -> bytes:
    if len(kcp_data) < 8:
        raise ValueError("Invalid archive header.")

    magic, orig_len = struct.unpack('<4sI', kcp_data[:8])
    if magic != b'KCP4':
        raise ValueError("Unsupported container format. Expected KCP4.")

    coder = ArithmeticOrder2Coder()
    idx = 8
    restored = bytearray()

    while idx < len(kcp_data):
        mode = kcp_data[idx]
        idx += 1

        if mode == 0x00:
            raw_len = struct.unpack('>H', kcp_data[idx : idx + 2])[0]
            idx += 2
            restored.extend(kcp_data[idx : idx + raw_len])
            idx += raw_len
        elif mode == 0x01:
            enc_len, raw_len = struct.unpack('>HH', kcp_data[idx : idx + 4])
            idx += 4
            enc_block = kcp_data[idx : idx + enc_len]
            restored.extend(coder.decompress_block(enc_block, raw_len))
            idx += enc_len
        elif mode == 0x02:
            enc_len, raw_len = struct.unpack('>HH', kcp_data[idx : idx + 4])
            idx += 4
            enc_block = kcp_data[idx : idx + enc_len]
            dec_delta = coder.decompress_block(enc_block, raw_len)
            restored.extend(inverse_delta_transform(dec_delta))
            idx += enc_len

    return bytes(restored)
