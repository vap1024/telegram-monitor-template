# Telegram Monitor Template

A small, clean-room Python template for monitoring message streams with transparent rules. It demonstrates classification, repost handling, and reviewable alert decisions using synthetic channels and values. It does not connect to a messaging service.

## Pipeline

1. Ingest messages in stable order and validate every field up front.
2. Classify with transparent keyword and regex rules. Every score is explainable from matched terms; there is no opaque model.
3. Deduplicate on normalized text fingerprints and shared links inside a time window. Expired keys are fresh messages.
4. Choose one action: alert, store, drop duplicate, or drop muted. Muting happens after scoring.
5. Emit alerts through a sink interface. The package has no network sender or credentials; a deployment can implement its own sink.
6. Render a deterministic report that can be diffed and audited.

Keyword matching is case-insensitive substring matching. A rule's weight contributes once when enough distinct keywords or regexes match. Rule order breaks category ties.

## Quick start

Requires Python 3.11 or newer. Runtime has no third-party dependencies.

```sh
python -m pip install -r requirements.txt
python examples/run_demo.py
python -m telegram_monitor.cli check --config examples/config.example.json --messages examples/messages.example.json
```

The install line adds pytest for development; package runtime uses only the standard library. The `tg-monitor demo` and `tg-monitor check` commands are available after installing the package.

## Configuration

`examples/config.example.json` shows four synthetic rules, an alert threshold of `2.0`, a 24-hour deduplication window, and a muted `digest` category. These values exist only to make the example outcomes visible. Configure your own rules and thresholds for your own stream.

For example, a minimal configuration can contain one rule and the policy fields:

```json
{"rules":[{"name":"launch-signals","category":"launch","keywords":["launch","mainnet"],"weight":1.0,"min_matches":1}],"alert_threshold":2.0,"dedup_window_hours":24,"muted_categories":["digest"]}
```

Messages are JSON objects with `id`, `channel`, `text`, and ISO-8601 `posted_at`; `links` and `views` are optional. URLs in text are extracted when links are omitted.

## Honest failure log

- A monitor that deduplicated on shared links alone glued hundreds of unrelated posts about one popular event into a single event and hid the distinct items inside it. Dedup now needs the window and keeps groups inspectable instead of silently swallowing posts.
- Keyword rules without a muted path alerted on every weekly digest that merely quoted the alert terms. Muting is a category decision made after scoring, so the score stays visible in the report.
- A duplicate check with no time window treated a genuine follow-up a week later as a repost. Windows expire; outside the window a repeat is news again.
- Scores that summed per keyword hit rewarded long posts for repeating one term. A rule now contributes its weight once, however many of its terms match.
- The first version sent alerts straight from the classifier, so a config typo went live instantly. Alerts now pass through a sink and a rendered report that can be reviewed before anything is sent.

## Limitations

This template reads JSON rather than connecting to a live feed. Substring rules can match incidental wording, timestamps should use consistent timezone conventions, and deduplication is an in-memory demonstration unless persisted state is explicitly saved. No sink in this package sends network traffic. Review rules, reports, and any deployment-specific output before use.

## Project layout

- `src/telegram_monitor/` contains models, rules, deduplication, pipeline, sinks, report, and CLI.
- `examples/` contains synthetic input and a fixed-time report demo.
- `tests/` covers validation, decisions, persistence, sinks, CLI, and determinism.

## Testing

Run `PYTHONPATH=src python -m pytest -q`. The GitHub Actions workflow runs the suite on Python 3.11 and 3.12 and checks that regenerated demo output is byte-identical.
