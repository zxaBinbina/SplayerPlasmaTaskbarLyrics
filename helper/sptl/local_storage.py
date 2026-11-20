# SPDX-License-Identifier: AGPL-3.0-only
"""Read Chromium localStorage without opening or locking its live LevelDB.
Only theme/settings records are exposed. Supports LevelDB WAL, SST and Snappy blocks.
"""
import json
import struct
from pathlib import Path

MAX_FILE = 64 * 1024 * 1024


def varint(data, pos=0):
    value = 0
    for shift in range(0, 70, 7):
        byte = data[pos]
        pos += 1
        value |= (byte & 127) << shift
        if byte < 128:
            return value, pos
    raise ValueError("invalid varint")


def snappy(data):
    size, pos = varint(data)
    if size > MAX_FILE:
        raise ValueError("snappy block too large")
    out = bytearray()
    while pos < len(data):
        tag = data[pos]
        pos += 1
        kind = tag & 3
        if kind == 0:
            length = tag >> 2
            if length >= 60:
                count = length - 59
                length = int.from_bytes(data[pos:pos + count], "little")
                pos += count
            length += 1
            out.extend(data[pos:pos + length])
            pos += length
        else:
            if kind == 1:
                length = 4 + ((tag >> 2) & 7)
                offset = ((tag & 224) << 3) | data[pos]
                pos += 1
            else:
                length = 1 + (tag >> 2)
                count = 2 if kind == 2 else 4
                offset = int.from_bytes(data[pos:pos + count], "little")
                pos += count
            if offset == 0 or offset > len(out):
                raise ValueError("invalid snappy copy")
            for _ in range(length):
                out.append(out[-offset])
        if len(out) > size:
            raise ValueError("invalid snappy length")
    if len(out) != size:
        raise ValueError("truncated snappy")
    return bytes(out)


def entries(block):
    if len(block) < 4:
        return
    restarts = struct.unpack("<I", block[-4:])[0]
    end = len(block) - 4 * (restarts + 1)
    if end < 0:
        raise ValueError("invalid block")
    pos, key = 0, b""
    while pos < end:
        shared, pos = varint(block, pos)
        length, pos = varint(block, pos)
        value_length, pos = varint(block, pos)
        if shared > len(key) or pos + length + value_length > end:
            raise ValueError("truncated block")
        key = key[:shared] + block[pos:pos + length]
        pos += length
        value = block[pos:pos + value_length]
        pos += value_length
        yield key, value


def block_at(data, handle):
    offset, pos = varint(handle)
    size, _ = varint(handle, pos)
    if offset + size + 5 > len(data):
        raise ValueError("invalid block handle")
    block = data[offset:offset + size]
    compression = data[offset + size]
    if compression not in (0, 1):
        raise ValueError("unsupported compression")
    return snappy(block) if compression else block


def table_records(data):
    if len(data) < 48 or data[-8:] != bytes.fromhex("57fb808b247547db"):
        return
    footer = data[-48:-8]
    _, pos = varint(footer)
    _, pos = varint(footer, pos)
    index = block_at(data, footer[pos:])
    for _, handle in entries(index):
        for key, value in entries(block_at(data, handle)):
            if len(key) >= 8:
                tag = int.from_bytes(key[-8:], "little")
                yield tag >> 8, tag & 255, key[:-8], value


def log_records(data):
    fragments = bytearray()
    for block_start in range(0, len(data), 32768):
        pos, end = block_start, min(block_start + 32768, len(data))
        while pos + 7 <= end:
            length = int.from_bytes(data[pos + 4:pos + 6], "little")
            kind = data[pos + 6]
            pos += 7
            if length == 0 or pos + length > end:
                break
            part = data[pos:pos + length]
            pos += length
            if kind == 1:
                yield from write_batch(part)
            elif kind == 2:
                fragments = bytearray(part)
            elif kind == 3:
                fragments.extend(part)
            elif kind == 4:
                fragments.extend(part)
                yield from write_batch(fragments)
                fragments.clear()


def write_batch(data):
    if len(data) < 12:
        return
    sequence, count = struct.unpack("<QI", data[:12])
    pos = 12
    for i in range(count):
        kind = data[pos]
        pos += 1
        key_length, pos = varint(data, pos)
        key = bytes(data[pos:pos + key_length])
        pos += key_length
        value = b""
        if kind == 1:
            value_length, pos = varint(data, pos)
            value = bytes(data[pos:pos + value_length])
            pos += value_length
        elif kind != 0:
            raise ValueError("invalid write batch")
        if pos > len(data):
            raise ValueError("truncated write batch")
        yield sequence + i, kind, key, value


def read_preferences(directory):
    latest = {}
    for path in sorted(Path(directory).glob("*")):
        if path.suffix not in (".log", ".ldb", ".sst"):
            continue
        try:
            if path.stat().st_size > MAX_FILE:
                continue
            data = path.read_bytes()
            records = log_records(data) if path.suffix == ".log" else table_records(data)
            for sequence, kind, key, value in records:
                if not key.startswith(b"_") or b"\x00\x01" not in key:
                    continue
                name = key.split(b"\x00\x01", 1)[1]
                if name not in (b"theme", b"settings"):
                    continue
                if sequence > latest.get(name, (-1, None))[0]:
                    latest[name] = (sequence, value if kind == 1 else None)
        except (OSError, ValueError, IndexError, struct.error):
            # A live write/compaction can leave a partial record; retry on the next refresh.
            continue
    result = {}
    for name, (_, value) in latest.items():
        if not value:
            continue
        try:
            text = value[1:].decode("utf-16-le" if value[0] == 0 else "latin1")
            decoded = json.loads(text)
            if isinstance(decoded, dict):
                result[name.decode()] = decoded
        except (ValueError, UnicodeError):
            continue
    return result
