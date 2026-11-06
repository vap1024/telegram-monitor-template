"""Local alert sink interfaces; deployments can provide their own sender."""

from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import Protocol

from .pipeline import ProcessedMessage


class AlertSink(Protocol):
    """Protocol for alert output; network implementations belong to deployers."""
    def emit(self, processed: ProcessedMessage) -> None:
        """Handle one processed alert."""
        ...


@dataclass
class CollectingSink:
    """Keep emitted alerts in memory for the demo and tests."""
    alerts: list[ProcessedMessage] = field(default_factory=list)

    def emit(self, processed: ProcessedMessage) -> None:
        """Append one alert to the in-memory collection."""
        self.alerts.append(processed)


class FileSink:
    """Append compact alert records locally; this class never sends over a network."""
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def emit(self, processed: ProcessedMessage) -> None:
        """Append one JSON line containing only alert summary fields."""
        record = {"id": processed.message.id, "channel": processed.message.channel,
                  "category": processed.classification.category, "score": processed.classification.score}
        with self.path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(record, sort_keys=True) + "\n")


def format_alert(processed: ProcessedMessage) -> str:
    """Format one alert as a compact single-line human-readable string."""
    return (f"[ALERT] {processed.message.channel}/{processed.classification.category} "
            f"score={processed.classification.score:.2f} {processed.message.id}")
