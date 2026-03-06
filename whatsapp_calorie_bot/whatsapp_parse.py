"""Parse WhatsApp exported chat .txt files and associate media."""

import hashlib
import logging
import re
from datetime import datetime, date
from pathlib import Path
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

# Android format: "1/27/26, 12:34 PM - Sender: Message"
# Also handles: "27/01/2026, 12:34 - Sender: Message"
ANDROID_PATTERN = re.compile(
    r"^(\d{1,2}/\d{1,2}/\d{2,4},\s*\d{1,2}:\d{2}(?::\d{2})?\s*(?:AM|PM|am|pm)?)\s*-\s*(.+?):\s(.+)$"
)

# iOS format: "[2026-01-27, 12:34:56] Sender: Message"
# Also: "[27/01/2026, 12:34:56 PM] Sender: Message"
IOS_PATTERN = re.compile(
    r"^\[(\d{1,4}[/.-]\d{1,2}[/.-]\d{1,4},?\s*\d{1,2}:\d{2}(?::\d{2})?\s*(?:AM|PM|am|pm)?)\]\s*(.+?):\s(.+)$"
)

# Media indicators
MEDIA_OMITTED_PATTERNS = [
    "<Media omitted>",
    "<media omitted>",
    "image omitted",
    "video omitted",
    "audio omitted",
    "sticker omitted",
    "GIF omitted",
    "document omitted",
]

# File attachment pattern: "IMG-20260227-WA0001.jpg (file attached)"
ATTACHED_FILE_RE = re.compile(r"([\w\-]+\.(?:jpg|jpeg|png|gif|webp|mp4|opus|pdf))\s*\(file attached\)", re.IGNORECASE)

# Common WhatsApp image filename patterns
WA_IMAGE_RE = re.compile(r"(IMG-\d{8}-WA\d+\.(?:jpg|jpeg|png|webp))", re.IGNORECASE)
PHOTO_RE = re.compile(r"((?:photo|image|IMG_)\S*\.(?:jpg|jpeg|png|webp))", re.IGNORECASE)

# Timestamp formats to try
TIMESTAMP_FORMATS = [
    "%m/%d/%y, %I:%M %p",      # US: 1/27/26, 12:34 PM
    "%m/%d/%y, %I:%M:%S %p",   # US with seconds
    "%d/%m/%y, %I:%M %p",      # EU: 27/01/26, 12:34 PM
    "%d/%m/%y, %H:%M",         # EU 24h: 27/01/26, 14:34
    "%m/%d/%Y, %I:%M %p",      # US 4-digit year
    "%d/%m/%Y, %I:%M %p",      # EU 4-digit year
    "%d/%m/%Y, %H:%M",         # EU 4-digit year 24h
    "%Y-%m-%d, %H:%M:%S",      # ISO-ish
    "%d/%m/%y, %I:%M:%S %p",   # EU with seconds
    "%d.%m.%y, %H:%M",         # German style
    "%d.%m.%Y, %H:%M",         # German style 4-digit year
]


def _parse_timestamp(ts_str: str, tz: ZoneInfo) -> datetime | None:
    """Try multiple formats to parse a WhatsApp timestamp."""
    ts_str = ts_str.strip().replace("\u202f", " ").replace("\xa0", " ")
    for fmt in TIMESTAMP_FORMATS:
        try:
            dt = datetime.strptime(ts_str, fmt)
            return dt.replace(tzinfo=tz)
        except ValueError:
            continue
    logger.warning("Could not parse timestamp: '%s'", ts_str)
    return None


def _compute_msg_id(timestamp: str, sender: str, text: str, media_paths: list[str]) -> str:
    """Compute a stable message ID from content."""
    parts = [timestamp, sender, text]
    for p in sorted(media_paths):
        try:
            h = hashlib.sha1(Path(p).read_bytes()).hexdigest()[:12]
        except (OSError, IOError):
            h = p
        parts.append(h)
    raw = "|".join(parts)
    return hashlib.sha1(raw.encode()).hexdigest()


def _find_chat_txt(extract_dir: Path) -> Path | None:
    """Find the WhatsApp chat .txt file in the extracted directory."""
    candidates = list(extract_dir.rglob("*.txt"))
    # Prefer files named _chat.txt or WhatsApp Chat
    for c in candidates:
        name_lower = c.name.lower()
        if "_chat" in name_lower or "whatsapp chat" in name_lower or "chat with" in name_lower:
            return c
    # Fall back to the largest .txt file
    if candidates:
        return max(candidates, key=lambda p: p.stat().st_size)
    return None


def _find_media_dir(extract_dir: Path) -> Path | None:
    """Find the media directory in the extracted archive."""
    for d in extract_dir.rglob("*"):
        if d.is_dir() and any(
            kw in d.name.lower() for kw in ("image", "media", "photo", "whatsapp")
        ):
            return d
    return extract_dir


def _find_media_file(filename: str, media_dir: Path, all_images: dict[str, Path]) -> Path | None:
    """Find a media file by name in the media directory."""
    # Exact match in index
    if filename in all_images:
        return all_images[filename]
    # Case-insensitive match
    filename_lower = filename.lower()
    for name, path in all_images.items():
        if name.lower() == filename_lower:
            return path
    return None


def _build_image_index(extract_dir: Path) -> dict[str, Path]:
    """Build an index of all image files by filename."""
    index: dict[str, Path] = {}
    for ext in ("*.jpg", "*.jpeg", "*.png", "*.webp", "*.gif"):
        for p in extract_dir.rglob(ext):
            index[p.name] = p
    # Also uppercase
    for ext in ("*.JPG", "*.JPEG", "*.PNG", "*.WEBP"):
        for p in extract_dir.rglob(ext):
            index[p.name] = p
    return index


def parse_whatsapp_export(
    extract_dir: Path,
    timezone: str = "America/Chicago",
    since: str | None = None,
    until: str | None = None,
    max_messages: int | None = None,
) -> list[dict]:
    """Parse a WhatsApp export directory into structured messages."""
    try:
        tz = ZoneInfo(timezone)
    except Exception:
        logger.warning("Invalid timezone '%s', falling back to America/Chicago.", timezone)
        tz = ZoneInfo("America/Chicago")

    since_date = date.fromisoformat(since) if since else None
    until_date = date.fromisoformat(until) if until else None

    chat_file = _find_chat_txt(extract_dir)
    if not chat_file:
        logger.error(
            "No WhatsApp chat .txt file found in %s. "
            "Expected a file like '_chat.txt' or 'WhatsApp Chat with *.txt'. "
            "Make sure you exported the chat from WhatsApp with the 'Export Chat' feature.",
            extract_dir,
        )
        return []

    logger.info("Using chat file: %s", chat_file)
    media_dir = _find_media_dir(extract_dir)
    image_index = _build_image_index(extract_dir)
    logger.info("Found %d image files in archive.", len(image_index))

    raw_lines = chat_file.read_text(encoding="utf-8", errors="replace").splitlines()
    messages: list[dict] = []
    current_msg: dict | None = None

    for line in raw_lines:
        parsed = _try_parse_line(line, tz)
        if parsed:
            # Save previous message
            if current_msg:
                _finalize_message(current_msg, image_index, media_dir)
                messages.append(current_msg)
            current_msg = parsed
        elif current_msg:
            # Continuation line
            current_msg["text"] += "\n" + line
            current_msg["raw_line"] += "\n" + line

    # Don't forget the last message
    if current_msg:
        _finalize_message(current_msg, image_index, media_dir)
        messages.append(current_msg)

    logger.info("Parsed %d raw messages from chat file.", len(messages))

    # Apply filters
    filtered = []
    for msg in messages:
        ts = msg.get("timestamp_dt")
        if ts:
            msg_date = ts.date()
            if since_date and msg_date < since_date:
                continue
            if until_date and msg_date > until_date:
                continue
        filtered.append(msg)
        if max_messages and len(filtered) >= max_messages:
            break

    logger.info("After filtering: %d messages.", len(filtered))

    # Compute IDs and clean up
    for msg in filtered:
        msg["msg_id"] = _compute_msg_id(
            msg["timestamp"], msg["sender"], msg["text"], msg["media_paths"]
        )
        # Remove internal fields
        msg.pop("timestamp_dt", None)

    return filtered


def _try_parse_line(line: str, tz: ZoneInfo) -> dict | None:
    """Try to parse a line as a new message. Returns dict or None."""
    for pattern in (ANDROID_PATTERN, IOS_PATTERN):
        m = pattern.match(line)
        if m:
            ts_str, sender, text = m.group(1), m.group(2), m.group(3)
            ts = _parse_timestamp(ts_str, tz)
            if ts:
                return {
                    "timestamp": ts.isoformat(),
                    "timestamp_dt": ts,
                    "sender": sender.strip(),
                    "text": text.strip(),
                    "has_media": False,
                    "media_paths": [],
                    "media_missing": False,
                    "raw_line": line,
                }
    return None


def _finalize_message(msg: dict, image_index: dict[str, Path], media_dir: Path | None) -> None:
    """Detect media references and link files."""
    text = msg["text"]

    # Check for <Media omitted>
    is_media_omitted = any(pat in text for pat in MEDIA_OMITTED_PATTERNS)

    # Check for file attachment references
    attached_match = ATTACHED_FILE_RE.search(text)
    wa_image_match = WA_IMAGE_RE.search(text)

    if attached_match:
        filename = attached_match.group(1)
        found = _find_media_file(filename, media_dir, image_index)
        if found:
            msg["has_media"] = True
            msg["media_paths"] = [str(found)]
        else:
            msg["has_media"] = True
            msg["media_paths"] = []
            msg["media_missing"] = True
            logger.debug("Referenced file not found: %s", filename)
    elif wa_image_match:
        filename = wa_image_match.group(1)
        found = _find_media_file(filename, media_dir, image_index)
        if found:
            msg["has_media"] = True
            msg["media_paths"] = [str(found)]
        else:
            msg["has_media"] = True
            msg["media_paths"] = []
            msg["media_missing"] = True
    elif is_media_omitted:
        msg["has_media"] = True
        msg["media_paths"] = []
        msg["media_missing"] = True
        logger.debug("Media omitted for message at %s", msg["timestamp"])
