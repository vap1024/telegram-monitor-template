"""Command-line entry points for demos and user-provided JSON inputs."""

import argparse
from datetime import datetime, timezone
from importlib.resources import files
import json
from pathlib import Path
import sys

from .config import config_from_json, load_config
from .model import Message
from .pipeline import run_pipeline
from .report import render_report

DEMO_NOW = "2026-11-09T09:06:00+00:00"
def _run_demo(out: str | None) -> int:
    data = files("telegram_monitor") / "data"
    config_path = data / "config.example.json"
    config = config_from_json(config_path.read_text(encoding="utf-8"))
    raw = json.loads((data / "messages.example.json").read_text(encoding="utf-8"))
    result = run_pipeline([Message.from_dict(item) for item in raw], config)
    report = render_report(result, DEMO_NOW)
    if out:
        Path(out).write_text(report, encoding="utf-8")
    else:
        print(report)
    return 0


def main(argv: list[str] | None = None) -> int:
    """Run demo or check commands, returning a shell status without tracebacks."""
    parser = argparse.ArgumentParser(prog="tg-monitor")
    commands = parser.add_subparsers(dest="command", required=True)
    demo = commands.add_parser("demo", help="run the bundled synthetic example")
    demo.add_argument("--out")
    check = commands.add_parser("check", help="process messages using a JSON config")
    check.add_argument("--config", required=True)
    check.add_argument("--messages", required=True)
    check.add_argument("--now", default=None, help="report timestamp (defaults to current UTC time)")
    args = parser.parse_args(argv)
    try:
        if args.command == "demo":
            return _run_demo(args.out)
        config = load_config(args.config)
        raw = json.loads(Path(args.messages).read_text(encoding="utf-8"))
        result = run_pipeline([Message.from_dict(item) for item in raw], config)
        now = args.now or datetime.now(timezone.utc).isoformat(timespec="seconds")
        print(render_report(result, now))
        return 0
    except (OSError, ValueError, KeyError, TypeError, AttributeError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
