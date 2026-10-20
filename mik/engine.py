"""Распаковка и сборка Amlogic-образа и ext4-разделов."""

import os
import shutil
import struct
import subprocess
import sys
from pathlib import Path

from mik.sparse import is_sparse, unsparse

def _root() -> Path:
    import sys

    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            return Path(meipass)
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]


ROOT = _root()


def packer_path() -> Path:
    candidates = [ROOT / "bin" / "aml_image_v2_packer"]
    if getattr(sys, "frozen", False):
        candidates.append(Path(sys.executable).resolve().parent / "bin" / "aml_image_v2_packer")
        candidates.append(Path(sys.executable).resolve().parent.parent / "Resources" / "bin" / "aml_image_v2_packer")
    candidates.append(Path(__file__).resolve().parents[1] / "bin" / "aml_image_v2_packer")
    for p in candidates:
        if p.is_file():
            return p
    return candidates[0]


PACKER = packer_path()
PART_DIRS = ("system", "vendor", "product", "odm")
EXT4_MAGIC_OFF = 0x438


def tool(name: str) -> str:
    for p in (
        Path("/opt/homebrew/opt/e2fsprogs/sbin") / name,
        Path("/usr/local/opt/e2fsprogs/sbin") / name,
        Path("/opt/homebrew/sbin") / name,
    ):
        if p.is_file():
            return str(p)
    found = shutil.which(name)
    if found:
        return found
    raise RuntimeError(f"нет {name}. Нужен e2fsprogs: brew install e2fsprogs")


def _run(cmd: list[str], cwd: Path | None = None) -> str:
    proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    out = (proc.stdout or "") + (proc.stderr or "")
    if proc.returncode != 0:
        raise RuntimeError(out.strip() or f"код {proc.returncode}: {' '.join(cmd)}")
    return out


def is_ext4(path: Path) -> bool:
    with path.open("rb") as f:
        f.seek(EXT4_MAGIC_OFF)
        return f.read(2) == b"\x53\xef"


def is_aml_image(path: Path) -> bool:
    if not path.is_file() or path.stat().st_size < 64:
        return False
    with path.open("rb") as f:
        magic = struct.unpack("<I", f.read(4))[0]
    # пакет v2, не sparse и не ext4
    if magic == 0xED26FF3A:
        return False
    try:
        with path.open("rb") as f:
            f.seek(EXT4_MAGIC_OFF)
            if f.read(2) == b"\x53\xef":
                return False
    except OSError:
        return False
    proc = subprocess.run([str(PACKER), "-c", str(path)], capture_output=True, text=True)
    text = (proc.stdout or "") + (proc.stderr or "")
    return proc.returncode == 0 and "ERR" not in text.splitlines()[0:3]


def _to_raw(src: Path, raw: Path) -> None:
    if is_sparse(src):
        unsparse(src, raw)
    else:
        shutil.copy2(src, raw)


def unpack_partition(src: Path, out_dir: Path, log) -> None:
    log(f"Выполняется распаковка образа раздела: {src.name}")
    if out_dir.exists():
        log("Обнаружена папка с распакованным образом раздела, удаляем!")
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)
    raw = out_dir.parent / f"{src.stem}.raw"
    _to_raw(src, raw)
    if not is_ext4(raw):
        raw.unlink(missing_ok=True)
        raise RuntimeError(f"Программа не умеет распаковывать: {src.name}")
    # debugfs: путь с пробелами — в кавычках
    _run([tool("debugfs"), "-R", f'rdump / "{out_dir}"', str(raw)])
    (out_dir / ".mik-size").write_text(str(raw.stat().st_size), encoding="utf-8")
    (out_dir / ".mik-label").write_text(src.stem, encoding="utf-8")
    raw.unlink(missing_ok=True)
    log(f"Действие по распаковки образа раздела: {src.name} завершено.")


def pack_partition(folder: Path, out_img: Path, log, extra_mb: int = 0, keep_size: bool = True) -> None:
    log(f"Выполняется сборка образа раздела: {out_img.name}")
    size_file = folder / ".mik-size"
    if keep_size and size_file.is_file():
        size = int(size_file.read_text().strip())
    else:
        size = 0
        for p in folder.rglob("*"):
            if p.is_file() and not p.name.startswith(".mik-"):
                size += p.stat().st_size
        size = max(size * 2, 8 * 1024 * 1024)
        # выравнивание на блок
        size = (size + 4095) & ~4095
    if extra_mb:
        size += extra_mb * 1024 * 1024
        size = (size + 4095) & ~4095
    label = (folder / ".mik-label").read_text().strip() if (folder / ".mik-label").is_file() else folder.name
    blocks = max(size // 4096, 64)
    staging = folder.parent / f".{folder.name}.staging"
    if staging.exists():
        shutil.rmtree(staging)
    shutil.copytree(folder, staging, ignore=shutil.ignore_patterns(".mik-size", ".mik-label"))
    tmp = out_img.with_suffix(out_img.suffix + ".tmp")
    tmp.unlink(missing_ok=True)
    log(f"Свободного места: считаем раздел {label}, {size // (1024 * 1024)} МБ")
    text = _run(
        [
            tool("mke2fs"),
            "-t",
            "ext4",
            "-b",
            "4096",
            "-L",
            label[:16],
            "-O",
            "^has_journal",
            "-d",
            str(staging),
            str(tmp),
            str(blocks),
        ]
    )
    shutil.rmtree(staging, ignore_errors=True)
    for line in text.splitlines():
        if "Exit" in line or "Creating" in line or "Created" in line or "error" in line.lower():
            log(line)
    tmp.replace(out_img)
    log(f"Действие по сборке образа раздела: {out_img.name} завершено.")
    log("Код выхода mke2fs: 0  (Completed successfully!)")


def unpack_firmware(img: Path, out_dir: Path, log, parts: set[str]) -> None:
    log(f"Выполняется распаковка образа прошивки: {img.name} Please wait...")
    if out_dir.exists():
        log("Обнаружена папка с распакованным образом прошивки, удаляем!")
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)
    text = _run([str(PACKER), "-d", str(img), str(out_dir)])
    for line in text.splitlines():
        if line.startswith("[Msg]") or "OK" in line or "ERR" in line:
            log(line)
    log(f"Действие по распаковки прошивки: {img.name} завершено.")
    for name in PART_DIRS:
        if name not in parts:
            continue
        part = out_dir / f"{name}.PARTITION"
        if not part.is_file():
            continue
        raw_check = out_dir / f".{name}.probe"
        try:
            if is_sparse(part):
                # только заголовок не читаем целиком дважды — unsparse внутри unpack
                pass
            elif not is_ext4(part):
                continue
        except OSError:
            continue
        try:
            unpack_partition(part, out_dir / name, log)
            raw_check.unlink(missing_ok=True)
        except RuntimeError as e:
            log(str(e))


def pack_firmware(folder: Path, out_img: Path, log, parts: set[str], extra_mb: int = 0, keep_size: bool = True) -> None:
    cfg = folder / "image.cfg"
    if not cfg.is_file():
        raise RuntimeError("не найдена инструкция для сборки образа!")
    for name in PART_DIRS:
        sub = folder / name
        part = folder / f"{name}.PARTITION"
        if name in parts and sub.is_dir():
            log(f"Переименовываем {name}.PARTITION — сборка из папки {name}")
            pack_partition(sub, part, log, extra_mb, keep_size)
    log(f"Выполняется сборка образа прошивки: {out_img.name} Please wait...")
    text = _run([str(PACKER), "-r", str(cfg), str(folder), str(out_img)])
    for line in text.splitlines():
        if "Pack Item" in line or "Pack image" in line or "ERR" in line or "OK" in line or "version:" in line:
            log(line)
    log(f"Действие по сборке прошивки: {out_img.name} завершено.")
    log("Код выхода AmlImagePack: 0  (Completed successfully!)")
