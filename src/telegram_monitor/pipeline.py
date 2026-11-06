"""Ordered message processing with one auditable action per input."""

from dataclasses import dataclass

from .classify import Classification, classify
from .config import MonitorConfig
from .dedup import DedupStore
from .model import Message


@dataclass(frozen=True)
class ProcessedMessage:
    """A message, its evidence, duplicate state, and final action."""
    message: Message
    classification: Classification
    is_duplicate: bool
    action: str


@dataclass(frozen=True)
class PipelineResult:
    """Stable ordered outcomes and action totals."""
    processed: tuple[ProcessedMessage, ...]
    counts: dict[str, int]


def run_pipeline(messages: list[Message] | tuple[Message, ...], config: MonitorConfig) -> PipelineResult:
    """Validate input, classify, deduplicate, choose actions, then store fresh items."""
    store = DedupStore(config.dedup_window_hours)
    actions = ("alert", "store", "drop_duplicate", "drop_muted")
    counts = {"total": len(messages), **{action: 0 for action in actions}}
    output: list[ProcessedMessage] = []
    for message in messages:
        classification = classify(message, config)
        duplicate = store.is_duplicate(message)
        if duplicate:
            action = "drop_duplicate"
        elif (classification.category in config.muted_categories and
              classification.score >= config.alert_threshold):
            action = "drop_muted"
        elif classification.is_alert:
            action = "alert"
        else:
            action = "store"
        output.append(ProcessedMessage(message, classification, duplicate, action))
        counts[action] += 1
        if not duplicate:
            store.add(message)
    return PipelineResult(tuple(output), counts)
