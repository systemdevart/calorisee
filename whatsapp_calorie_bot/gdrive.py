"""Download files from Google Drive."""

import logging
import re
from pathlib import Path

import gdown

logger = logging.getLogger(__name__)

GDRIVE_FILE_ID_RE = re.compile(r"/d/([a-zA-Z0-9_-]+)")


def extract_file_id(url: str) -> str:
    """Extract the file ID from a Google Drive URL."""
    m = GDRIVE_FILE_ID_RE.search(url)
    if not m:
        raise ValueError(f"Could not extract file ID from URL: {url}")
    return m.group(1)


def download_gdrive_file(url: str, dest_dir: Path) -> Path:
    """Download a file from Google Drive to dest_dir. Returns path to downloaded file."""
    file_id = extract_file_id(url)
    download_url = f"https://drive.google.com/uc?id={file_id}"

    # gdown will auto-detect filename; we use a temp name then rename
    output_path = str(dest_dir / "archive")
    logger.info("Downloading file ID %s ...", file_id)

    try:
        result = gdown.download(download_url, output_path, quiet=False, fuzzy=True)
    except Exception as e:
        raise RuntimeError(
            f"Failed to download from Google Drive. "
            f"Ensure the link is set to 'Anyone with the link' sharing. "
            f"URL: {url}\n"
            f"Error: {e}"
        ) from e

    if result is None:
        raise RuntimeError(
            f"Failed to download from Google Drive (returned None). "
            f"Ensure the link is publicly shared. URL: {url}"
        )

    downloaded = Path(result)
    logger.info("Download complete: %s (%.1f MB)", downloaded.name, downloaded.stat().st_size / 1e6)
    return downloaded
