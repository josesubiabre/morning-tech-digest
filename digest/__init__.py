"""Armado del digest: selección/validación y formato del mensaje."""

from digest.selection import drop_recent_duplicates, validate_noticias
from digest.formatter import build_whatsapp_message, save_digest_to_history

__all__ = [
    "drop_recent_duplicates",
    "validate_noticias",
    "build_whatsapp_message",
    "save_digest_to_history",
]
