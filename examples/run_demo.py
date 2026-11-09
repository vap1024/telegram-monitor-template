"""Run the bundled synthetic configuration and messages without installation."""

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from telegram_monitor.config import load_config
from telegram_monitor.model import Message
from telegram_monitor.pipeline import run_pipeline
from telegram_monitor.report import render_report

NOW = "2026-11-09T09:06:00+00:00"


def main() -> int:
    """Render the fixed-time example report to stdout or an output file."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--out")
    args = parser.parse_args()
    config = load_config(ROOT / "examples/config.example.json")
    raw = json.loads((ROOT / "examples/messages.example.json").read_text(encoding="utf-8"))
    result = run_pipeline([Message.from_dict(row) for row in raw], config)
    report = render_report(result, NOW)
    if args.out:
        Path(args.out).write_text(report, encoding="utf-8")
    else:
        print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
