"""Android sparse image <-> raw."""

import struct
from pathlib import Path

MAGIC = 0xED26FF3A
CHUNK_RAW = 0xCAC1
CHUNK_FILL = 0xCAC2
CHUNK_DONT_CARE = 0xCAC3
CHUNK_CRC = 0xCAC4


def is_sparse(path: Path) -> bool:
    with path.open("rb") as f:
        raw = f.read(4)
    if len(raw) < 4:
        return False
    return struct.unpack("<I", raw)[0] == MAGIC


def unsparse(src: Path, dst: Path) -> int:
    with src.open("rb") as f:
        hdr = f.read(28)
        if len(hdr) < 28:
            raise RuntimeError("короткий sparse-заголовок")
        magic, major, minor, file_hdr_sz, chunk_hdr_sz, blk_sz, total_blks, total_chunks, _crc = struct.unpack(
            "<IHHHHIIII", hdr
        )
        if magic != MAGIC:
            raise RuntimeError("это не Android sparse")
        if file_hdr_sz > 28:
            f.read(file_hdr_sz - 28)
        dst.parent.mkdir(parents=True, exist_ok=True)
        written = 0
        with dst.open("wb") as out:
            for _ in range(total_chunks):
                ch = f.read(chunk_hdr_sz)
                if len(ch) < 12:
                    raise RuntimeError("битый chunk")
                ctype, _res, chunk_blks, total_sz = struct.unpack("<HHII", ch[:12])
                data_sz = total_sz - chunk_hdr_sz
                payload = f.read(data_sz) if data_sz else b""
                if ctype == CHUNK_RAW:
                    out.write(payload)
                    written += len(payload)
                elif ctype == CHUNK_FILL:
                    if len(payload) < 4:
                        raise RuntimeError("fill chunk")
                    fill = payload[:4]
                    out.write(fill * chunk_blks * (blk_sz // 4))
                    written += chunk_blks * blk_sz
                elif ctype == CHUNK_DONT_CARE:
                    out.seek(chunk_blks * blk_sz, 1)
                    written += chunk_blks * blk_sz
                elif ctype == CHUNK_CRC:
                    continue
                else:
                    raise RuntimeError(f"неизвестный chunk {ctype:#x}")
            out.truncate(total_blks * blk_sz)
    return total_blks * blk_sz
