"""Validated input message model and URL extraction helpers."""

from dataclasses import dataclass
from datetime import datetime
import re
from typing import Any

_URL_RE = re.compile(r"https?://[^\s<>\]\[{}\"']+", re.IGNORECASE)


def extract_links(text: str) -> tuple[str, ...]:
    """Return distinct HTTP(S) URLs in appearance order, trimming sentence punctuation."""
    found: list[str] = []
    for match in _URL_RE.findall(text):
        url = match.rstrip(".,!?;:)")
        if url and url not in found:
            found.append(url)
    return tuple(found)


@dataclass(frozen=True)
class Message:
    """One validated, timestamped message from a synthetic channel."""

    id: str
    channel: str
    text: str
    posted_at: str
    links: tuple[str, ...] = ()
    views: int | None = None

    def __post_init__(self) -> None:
        """Reject missing identity/content and timestamps that cannot be parsed."""
        for field in ("id", "channel", "text"):
            if not isinstance(getattr(self, field), str) or not getattr(self, field).strip():
                raise ValueError(f"{field} must not be empty")
        if not isinstance(self.posted_at, str):
            raise ValueError("posted_at must be a valid ISO-8601 timestamp")
        try:
            datetime.fromisoformat(self.posted_at.replace("Z", "+00:00"))
        except (TypeError, ValueError) as exc:
            raise ValueError("posted_at must be a valid ISO-8601 timestamp") from exc
        object.__setattr__(self, "links", tuple(self.links) or extract_links(self.text))

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "Message":
        """Create a message from a JSON-compatible mapping."""
        return cls(id=value["id"], channel=value["channel"], text=value["text"],
                   posted_at=value["posted_at"], links=tuple(value.get("links", ())),
                   views=value.get("views"))

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-compatible representation."""
        return {"id": self.id, "channel": self.channel, "text": self.text,
                "posted_at": self.posted_at, "links": list(self.links), "views": self.views}
