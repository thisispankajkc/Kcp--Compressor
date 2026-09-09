from kcp import compress_to_kcp, decompress_from_kcp

# Read raw bytes
with open("sample.bin", "rb") as f:
    data = f.read()

# Compress
compressed = compress_to_kcp(data)

# Restore
original = decompress_from_kcp(compressed)
assert original == data