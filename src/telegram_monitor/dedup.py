"""Windowed text and link deduplication with inspectable persisted state."""

from datetime import datetime, timedelta
import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urlsplit

from .model import Message


def _parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _clean_text(text: str) -> str:
    """Normalize text after removing URLs and punctuation-only noise."""
    clean = re.sub(r"https?://\S+", " ", text, flags=re.IGNORECASE)
    clean = re.sub(r"[^\w\s]", " ", clean.casefold())
    return " ".join(clean.split())


def fingerprint_of(text: str) -> str:
    """Hash case/space normalized text with URLs and punctuation-only noise removed."""
    return hashlib.sha256(_clean_text(text).encode("utf-8")).hexdigest()[:16]


def _link_key(link: str) -> str:
    parts = urlsplit(link if "://" in link else "https://" + link)
    return (parts.netloc + parts.path).casefold().rstrip("/")


def bridge_keys(message: Message) -> frozenset[str]:
    """Return a text fingerprint key and normalized keys for every shared link."""
    keys = {"link:" + _link_key(link) for link in message.links}
    clean = _clean_text(message.text)
    if clean:
        keys.add("text:" + fingerprint_of(message.text))
    return frozenset(keys)


class DedupStore:
    """In-memory first-seen keys; persisted state is plain JSON."""
    def __init__(self, dedup_window_hours: float = 24.0) -> None:
        self.dedup_window_hours = dedup_window_hours
        self.entries: dict[str, dict[str, str]] = {}

    def seen(self, message: Message) -> bool:
        """Check whether a bridge key is recorded, without changing state."""
        return any(key in self.entries for key in bridge_keys(message))

    def add(self, message: Message) -> None:
        """Record every bridge key once, preserving its first message and time."""
        current = _parse_time(message.posted_at)
        window = timedelta(hours=self.dedup_window_hours)
        for key in bridge_keys(message):
            entry = self.entries.get(key)
            if entry is None or current - _parse_time(entry["posted_at"]) > window:
                self.entries[key] = {"id": message.id, "posted_at": message.posted_at}

    def is_duplicate(self, message: Message) -> bool:
        """Check for any previously recorded key still within the configured window."""
        current = _parse_time(message.posted_at)
        window = timedelta(hours=self.dedup_window_hours)
        for key in bridge_keys(message):
            entry = self.entries.get(key)
            if entry and timedelta(0) <= current - _parse_time(entry["posted_at"]) <= window:
                return True
        return False

    def prune(self, now_iso: str, window_hours: float) -> None:
        """Drop keys whose first-seen timestamp is older than the supplied window."""
        now = _parse_time(now_iso)
        window = timedelta(hours=window_hours)
        self.entries = {key: value for key, value in self.entries.items()
                        if now - _parse_time(value["posted_at"]) <= window}

    def save(self, path: str | Path) -> None:
        """Write dedup state as deterministic JSON."""
        Path(path).write_text(json.dumps(self.entries, sort_keys=True, indent=2) + "\n", encoding="utf-8")

    @classmethod
    def load(cls, path: str | Path, dedup_window_hours: float = 24.0) -> "DedupStore":
        """Read dedup state previously written by save."""
        store = cls(dedup_window_hours)
        store.entries = json.loads(Path(path).read_text(encoding="utf-8"))
        return store


def group_duplicates(messages: list[Message], window_hours: float) -> list[list[str]]:
    """Group input-ordered message ids that share a key within the time window."""
    groups: list[list[str]] = []
    used: set[str] = set()
    for index, message in enumerate(messages):
        if message.id in used:
            continue
        cluster = [message]
        keys = bridge_keys(message)
        for candidate in messages[index + 1:]:
            if candidate.id in used or not keys.intersection(bridge_keys(candidate)):
                continue
            delta = _parse_time(candidate.posted_at) - _parse_time(message.posted_at)
            if timedelta(0) <= delta <= timedelta(hours=window_hours):
                cluster.append(candidate)
        if len(cluster) > 1:
            groups.append([item.id for item in cluster])
            used.update(item.id for item in cluster)
    return groups
