"""Pure, explainable classification from transparent configured rules."""

from dataclasses import dataclass
import re

from .config import MonitorConfig
from .model import Message


@dataclass(frozen=True)
class Classification:
    """Score and matching evidence for a message."""
    category: str | None
    score: float
    matched_rules: tuple[str, ...]
    matched_terms: tuple[str, ...]
    is_alert: bool


def classify(message: Message, config: MonitorConfig) -> Classification:
    """Score each firing rule once and apply threshold and mute policy."""
    fired: list[tuple[str, str, float]] = []
    terms: set[str] = set()
    for rule in config.rules:
        hits: set[str] = set()
        for keyword in rule.keywords:
            if keyword.casefold() in message.text.casefold():
                hits.add(keyword)
        for pattern in rule.patterns:
            if re.search(pattern, message.text, re.IGNORECASE):
                hits.add(f"/{pattern}/")
        if len(hits) >= rule.min_matches:
            fired.append((rule.name, rule.category, rule.weight))
            terms.update(hits)
    score = float(sum(item[2] for item in fired))
    category = max(enumerate(fired), key=lambda pair: (pair[1][2], -pair[0]))[1][1] if fired else None
    alert = category is not None and score >= config.alert_threshold and category not in config.muted_categories
    return Classification(category, score, tuple(item[0] for item in fired), tuple(sorted(terms)), alert)
