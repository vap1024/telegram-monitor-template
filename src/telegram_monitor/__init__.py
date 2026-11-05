"""Public API for the synthetic channel monitor template."""

from .classify import Classification, classify
from .config import MonitorConfig, Rule, load_config, validate_config
from .dedup import DedupStore, bridge_keys, fingerprint_of, group_duplicates
from .model import Message, extract_links
from .pipeline import PipelineResult, ProcessedMessage, run_pipeline
from .report import render_report

__version__ = "0.1.0"

__all__ = [
    "Classification", "DedupStore", "Message", "MonitorConfig", "PipelineResult",
    "ProcessedMessage", "Rule", "bridge_keys", "classify", "extract_links",
    "fingerprint_of", "group_duplicates", "load_config", "render_report",
    "run_pipeline", "validate_config",
]
