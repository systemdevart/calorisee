"""Extract archive files (zip, rar, 7z)."""

import logging
import zipfile
from pathlib import Path

logger = logging.getLogger(__name__)


def detect_format(archive_path: Path) -> str:
    """Detect archive format from file extension or magic bytes."""
    suffix = archive_path.suffix.lower()
    # Also check if gdown stripped the extension
    if suffix in (".zip",):
        return "zip"
    if suffix in (".rar",):
        return "rar"
    if suffix in (".7z",):
        return "7z"

    # Try magic bytes
    with open(archive_path, "rb") as f:
        header = f.read(8)
    if header[:4] == b"PK\x03\x04":
        return "zip"
    if header[:7] == b"Rar!\x1a\x07\x00" or header[:8] == b"Rar!\x1a\x07\x01\x00":
        return "rar"
    if header[:6] == b"7z\xbc\xaf\x27\x1c":
        return "7z"

    # Default: try zip
    return "zip"


def extract_archive(archive_path: Path, dest_dir: Path) -> None:
    """Extract an archive to dest_dir."""
    fmt = detect_format(archive_path)
    logger.info("Detected format: %s", fmt)

    if fmt == "zip":
        _extract_zip(archive_path, dest_dir)
    elif fmt == "rar":
        _extract_rar(archive_path, dest_dir)
    elif fmt == "7z":
        _extract_7z(archive_path, dest_dir)
    else:
        raise ValueError(f"Unsupported archive format: {fmt}")

    # Log what was extracted
    files = list(dest_dir.rglob("*"))
    logger.info("Extracted %d files/directories.", len(files))


def _extract_zip(archive_path: Path, dest_dir: Path) -> None:
    try:
        with zipfile.ZipFile(archive_path, "r") as zf:
            zf.extractall(dest_dir)
    except zipfile.BadZipFile as e:
        raise RuntimeError(f"Bad zip file: {archive_path}. Error: {e}") from e


def _extract_rar(archive_path: Path, dest_dir: Path) -> None:
    import subprocess

    try:
        subprocess.run(["unrar", "x", "-o+", str(archive_path), str(dest_dir) + "/"], check=True)
    except FileNotFoundError:
        raise RuntimeError(
            "Cannot extract .rar files: 'unrar' not found. "
            "Install it with: sudo apt install unrar (Linux) or brew install unrar (macOS)"
        )


def _extract_7z(archive_path: Path, dest_dir: Path) -> None:
    import subprocess

    try:
        subprocess.run(["7z", "x", str(archive_path), f"-o{dest_dir}", "-y"], check=True)
    except FileNotFoundError:
        raise RuntimeError(
            "Cannot extract .7z files: '7z' not found. "
            "Install it with: sudo apt install p7zip-full (Linux) or brew install p7zip (macOS)"
        )
