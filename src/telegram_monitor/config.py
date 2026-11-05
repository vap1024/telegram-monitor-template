"""Configuration models and JSON loading with explicit validation."""

from dataclasses import dataclass
import json
import math
import re
from pathlib import Path


@dataclass(frozen=True)
class Rule:
    """One transparent scoring rule; keywords match as case-insensitive substrings."""
    name: str
    category: str
    keywords: tuple[str, ...] = ()
    patterns: tuple[str, ...] = ()
    weight: float = 1.0
    min_matches: int = 1


@dataclass(frozen=True)
class MonitorConfig:
    """Rules and policy thresholds for a monitor run."""
    rules: tuple[Rule, ...]
    alert_threshold: float
    dedup_window_hours: float
    muted_categories: tuple[str, ...] = ()


def validate_config(config: MonitorConfig) -> None:
    """Validate names, matching expressions, and policy limits."""
    if not config.rules:
        raise ValueError("rules must contain at least one rule")
    names: set[str] = set()
    for rule in config.rules:
        if not isinstance(rule.name, str):
            raise ValueError("rule.name must be a string")
        if not rule.name.strip():
            raise ValueError("rule.name must not be empty")
        if rule.name in names:
            raise ValueError(f"duplicate rule.name: {rule.name}")
        names.add(rule.name)
        if not isinstance(rule.category, str):
            raise ValueError(f"rule.category must be a string ({rule.name})")
        if not rule.category.strip():
            raise ValueError(f"rule.category must not be empty ({rule.name})")
        if not rule.keywords and not rule.patterns:
            raise ValueError(f"rule {rule.name} needs keywords or patterns")
        for keyword in rule.keywords:
            if not isinstance(keyword, str) or not keyword.strip():
                raise ValueError(f"rule.keywords must contain non-empty strings ({rule.name})")
        for pattern in rule.patterns:
            if not isinstance(pattern, str) or not pattern.strip():
                raise ValueError(f"rule.patterns must contain non-empty strings ({rule.name})")
            try:
                re.compile(pattern)
            except re.error as exc:
                raise ValueError(f"rule.patterns invalid regex in {rule.name}: {exc}") from exc
        if not math.isfinite(rule.weight):
            raise ValueError(f"rule.weight must be finite ({rule.name})")
        if rule.weight <= 0:
            raise ValueError(f"rule.weight must be positive ({rule.name})")
        if rule.min_matches < 1:
            raise ValueError(f"rule.min_matches must be at least 1 ({rule.name})")
    if not math.isfinite(config.alert_threshold):
        raise ValueError("alert_threshold must be finite")
    if config.alert_threshold < 0:
        raise ValueError("alert_threshold must not be negative")
    if not math.isfinite(config.dedup_window_hours):
        raise ValueError("dedup_window_hours must be finite")
    if config.dedup_window_hours <= 0:
        raise ValueError("dedup_window_hours must be positive")
    if len(set(config.muted_categories)) != len(config.muted_categories):
        raise ValueError("muted_categories must not contain duplicates")


def load_config(path: str | Path) -> MonitorConfig:
    """Load and validate a JSON configuration file."""
    return config_from_json(Path(path).read_text(encoding="utf-8"))


def config_from_json(text: str) -> MonitorConfig:
    """Load and validate configuration from JSON text."""
    raw = json.loads(text)
    for item in raw["rules"]:
        for field in ("keywords", "patterns"):
            if isinstance(item.get(field, ()), str):
                raise ValueError(f"rule.{field} must be a list")
    if isinstance(raw.get("muted_categories", ()), str):
        raise ValueError("muted_categories must be a list")
    rules = tuple(Rule(name=item["name"], category=item["category"],
                       keywords=tuple(item.get("keywords", ())),
                       patterns=tuple(item.get("patterns", ())),
                       weight=float(item.get("weight", 1.0)),
                       min_matches=int(item.get("min_matches", 1))) for item in raw["rules"])
    config = MonitorConfig(rules, float(raw["alert_threshold"]),
                           float(raw["dedup_window_hours"]),
                           tuple(raw.get("muted_categories", ())))
    validate_config(config)
    return config
