"""Acceptance coverage for the package's public behavior."""

import json
from pathlib import Path
import subprocess
import sys

import pytest

from telegram_monitor.classify import classify
from telegram_monitor.config import MonitorConfig, Rule, load_config, validate_config
from telegram_monitor.dedup import DedupStore, bridge_keys, fingerprint_of, group_duplicates
from telegram_monitor.model import Message, extract_links
from telegram_monitor.pipeline import run_pipeline
from telegram_monitor.report import render_report
from telegram_monitor.sinks import CollectingSink, FileSink, format_alert

ROOT = Path(__file__).resolve().parents[1]
BASE = "2026-11-01T09:00:00+00:00"


def msg(text="launch ready", ident="a", at=BASE, links=(), channel="example-news"):
    return Message(ident, channel, text, at, links)


def config(rules=None, threshold=2.0, muted=(), window=24):
    return MonitorConfig(tuple(rules or [Rule("launch", "launch", ("launch",), weight=2)]),
                         threshold, window, tuple(muted))


def test_model_empty_id():
    with pytest.raises(ValueError, match="id"):
        Message("", "c", "x", BASE)


def test_model_empty_channel():
    with pytest.raises(ValueError, match="channel"):
        Message("i", "", "x", BASE)


def test_model_empty_text():
    with pytest.raises(ValueError, match="text"):
        Message("i", "c", "", BASE)


def test_model_bad_timestamp():
    with pytest.raises(ValueError, match="posted_at"):
        Message("i", "c", "x", "not-a-date")


def test_model_non_string_timestamp():
    with pytest.raises(ValueError, match="posted_at"):
        Message("i", "c", "x", 123)


def test_model_round_trip():
    item = Message("i", "c", "x", BASE, ("https://sample.invalid/a",), 3)
    assert Message.from_dict(item.to_dict()) == item


def test_extract_links():
    assert extract_links("See https://sample.invalid/a, then http://example.invalid/b!") == (
        "https://sample.invalid/a", "http://example.invalid/b")


def test_config_no_rules():
    with pytest.raises(ValueError, match="rules"):
        validate_config(MonitorConfig((), 1, 2))


def test_config_duplicate_names():
    rule = Rule("x", "c", ("x",))
    with pytest.raises(ValueError, match="duplicate"):
        validate_config(MonitorConfig((rule, rule), 1, 2))


def test_config_empty_name():
    with pytest.raises(ValueError, match="rule.name"):
        validate_config(config([Rule("", "c", ("x",))]))


def test_config_empty_category():
    with pytest.raises(ValueError, match="rule.category"):
        validate_config(config([Rule("x", "", ("x",))]))


def test_config_no_matchers():
    with pytest.raises(ValueError, match="keywords or patterns"):
        validate_config(config([Rule("x", "c")]))


def test_config_invalid_regex():
    with pytest.raises(ValueError, match="regex"):
        validate_config(config([Rule("x", "c", patterns=("[",))]))


def test_config_nonpositive_weight():
    with pytest.raises(ValueError, match="weight"):
        validate_config(config([Rule("x", "c", ("x",), weight=0)]))


def test_config_bad_min_matches():
    with pytest.raises(ValueError, match="min_matches"):
        validate_config(config([Rule("x", "c", ("x",), min_matches=0)]))


def test_config_negative_threshold():
    with pytest.raises(ValueError, match="alert_threshold"):
        validate_config(config(threshold=-1))


def test_config_nonpositive_window():
    with pytest.raises(ValueError, match="dedup_window_hours"):
        validate_config(config(window=0))


def test_config_duplicate_muted():
    with pytest.raises(ValueError, match="muted_categories"):
        validate_config(config(muted=("x", "x")))


def test_config_json_load():
    assert load_config(ROOT / "examples/config.example.json").alert_threshold == 2


def test_config_string_keywords_rejected(tmp_path):
    path = tmp_path / "config.json"
    path.write_text('{"rules":[{"name":"x","category":"c","keywords":"launch"}],"alert_threshold":1,"dedup_window_hours":24}')
    with pytest.raises(ValueError, match="keywords"):
        load_config(path)


def test_config_empty_keyword_rejected():
    with pytest.raises(ValueError, match="keywords"):
        validate_config(config([Rule("x", "c", ("",))]))


def test_config_nan_weight_rejected():
    with pytest.raises(ValueError, match="weight"):
        validate_config(config([Rule("x", "c", ("x",), weight=float("nan"))]))


def test_classify_single_rule():
    got = classify(msg("LAUNCH update"), config())
    assert (got.score, got.category, got.is_alert) == (2, "launch", True)


def test_classify_sums_rules_once():
    rules = [Rule("a", "one", ("launch", "ready"), weight=1), Rule("b", "two", ("ready",), weight=3)]
    got = classify(msg("launch ready ready"), config(rules))
    assert got.score == 4 and got.matched_rules == ("a", "b")


def test_classify_min_matches():
    rule = Rule("a", "one", ("launch", "ready"), min_matches=2)
    assert classify(msg("launch only"), config([rule], threshold=0)).category is None


def test_classify_min_matches_positive_case():
    rule = Rule("a", "one", ("launch", "ready"), min_matches=2)
    assert classify(msg("launch only"), config([rule], threshold=0)).category is None
    assert classify(msg("launch is ready"), config([rule], threshold=0)).category == "one"


def test_classify_muted_suppresses_alert():
    got = classify(msg(), config(muted=("launch",)))
    assert not got.is_alert and got.score == 2


def test_classify_tie_uses_first():
    rules = [Rule("a", "first", ("launch",), weight=2), Rule("b", "second", ("launch",), weight=2)]
    assert classify(msg(), config(rules)).category == "first"


def test_classify_no_match():
    got = classify(msg("nothing here"), config())
    assert got.category is None and got.score == 0 and not got.is_alert


def test_fingerprint_normalizes_case_space_and_url():
    assert fingerprint_of("Hello  WORLD https://sample.invalid/a") == fingerprint_of("hello world")


def test_fingerprint_ignores_punctuation_noise():
    assert fingerprint_of("launch!!!") == fingerprint_of("launch")


def test_fingerprint_different_text():
    assert fingerprint_of("alpha") != fingerprint_of("beta")


def test_bridge_keys_normalize_url():
    one = bridge_keys(msg("first", links=("https://sample.invalid/path/?q=1",)))
    two = bridge_keys(msg("second", links=("http://sample.invalid/path",)))
    assert "link:sample.invalid/path" in one & two


def test_dedup_inside_window():
    store = DedupStore(24)
    store.add(msg("same"))
    assert store.is_duplicate(msg("same", "b", "2026-11-02T08:00:00+00:00"))


def test_dedup_outside_window():
    store = DedupStore(24)
    store.add(msg("same"))
    assert not store.is_duplicate(msg("same", "b", "2026-11-03T09:00:00+00:00"))


def test_dedup_restarts_after_window():
    store = DedupStore(24)
    store.add(msg("same", "a"))
    at_25 = msg("same", "b", "2026-11-02T10:00:00+00:00")
    assert not store.is_duplicate(at_25)
    store.add(at_25)
    assert store.entries["text:" + fingerprint_of("same")]["id"] == "b"
    assert store.is_duplicate(msg("same", "c", "2026-11-02T11:00:00+00:00"))


def test_dedup_third_copy_is_duplicate():
    items = [msg("same", "a"), msg("same", "b", "2026-11-01T10:00:00+00:00"),
             msg("same", "c", "2026-11-01T11:00:00+00:00")]
    result = run_pipeline(items, config(threshold=100))
    assert [item.is_duplicate for item in result.processed] == [False, True, True]


def test_url_only_text_uses_link_keys_only():
    one = msg("https://sample.invalid/a", "a")
    other = msg("https://sample.invalid/b", "b")
    same = msg("https://sample.invalid/a", "c")
    store = DedupStore()
    store.add(one)
    assert not store.is_duplicate(other)
    assert store.is_duplicate(same)


def test_dedup_seen_does_not_add():
    store = DedupStore()
    assert not store.seen(msg())
    store.add(msg())
    assert store.seen(msg())


def test_dedup_save_load_round_trip(tmp_path):
    store = DedupStore(12)
    store.add(msg())
    path = tmp_path / "state.json"
    store.save(path)
    assert DedupStore.load(path, 12).entries == store.entries


def test_dedup_prune():
    store = DedupStore()
    store.add(msg())
    store.prune("2026-11-03T09:00:00+00:00", 24)
    assert not store.entries


def test_group_duplicates():
    items = [msg("same", "a"), msg("same", "b", "2026-11-01T10:00:00+00:00"), msg("other", "c")]
    assert group_duplicates(items, 24) == [["a", "b"]]


def demo_result():
    cfg = load_config(ROOT / "examples/config.example.json")
    rows = json.loads((ROOT / "examples/messages.example.json").read_text())
    return run_pipeline([Message.from_dict(row) for row in rows], cfg)


def test_pipeline_has_all_actions_and_counts():
    result = demo_result()
    assert all(result.counts[action] > 0 for action in ("alert", "store", "drop_duplicate", "drop_muted"))
    assert result.counts["total"] == 8


def test_pipeline_action_order():
    result = demo_result()
    assert [item.action for item in result.processed] == ["alert", "drop_duplicate", "store", "drop_duplicate",
                                                        "drop_muted", "store", "alert", "alert"]


def test_collecting_sink():
    sink = CollectingSink()
    alert = next(item for item in demo_result().processed if item.action == "alert")
    sink.emit(alert)
    assert sink.alerts == [alert]


def test_file_sink_json_lines(tmp_path):
    path = tmp_path / "alerts.jsonl"
    alert = next(item for item in demo_result().processed if item.action == "alert")
    FileSink(path).emit(alert)
    row = json.loads(path.read_text().strip())
    assert row["id"] == alert.message.id and row["category"] == "launch"


def test_format_alert():
    alert = next(item for item in demo_result().processed if item.action == "alert")
    assert format_alert(alert).startswith("[ALERT] example-news/launch score=2.00 m01")


def test_report_sections_order_and_content():
    report = render_report(demo_result(), "2026-11-09T09:06:00+00:00")
    sections = ["# Monitor demo report", "## Summary", "## Alerts", "## Stored",
                "## Dropped duplicates", "## Dropped muted", "## Method notes"]
    assert [report.index(section) for section in sections] == sorted(report.index(section) for section in sections)
    assert "Run date: 2026-11-09T09:06:00+00:00" in report and "m08" in report


def test_cli_demo():
    run = subprocess.run([sys.executable, "-m", "telegram_monitor.cli", "demo"], cwd=ROOT,
                         env={**__import__("os").environ, "PYTHONPATH": "src"}, capture_output=True, text=True)
    assert run.returncode == 0 and "## Alerts" in run.stdout


def test_cli_check_and_error(tmp_path):
    env = {**__import__("os").environ, "PYTHONPATH": "src"}
    good = subprocess.run([sys.executable, "-m", "telegram_monitor.cli", "check", "--config",
                           "examples/config.example.json", "--messages", "examples/messages.example.json"],
                          cwd=ROOT, env=env, capture_output=True, text=True)
    bad = subprocess.run([sys.executable, "-m", "telegram_monitor.cli", "check", "--config",
                          str(tmp_path / "absent.json"), "--messages", "absent.json"],
                         cwd=ROOT, env=env, capture_output=True, text=True)
    assert good.returncode == 0 and bad.returncode == 2 and bad.stderr.startswith("error: ")


@pytest.mark.parametrize("kind", ["message", "config"])
def test_cli_bad_input_has_no_traceback(tmp_path, kind):
    config_path = tmp_path / "config.json"
    config_path.write_text('{"rules":[{"name":7,"category":"c","keywords":["x"]}],"alert_threshold":1,"dedup_window_hours":24}')
    messages_path = tmp_path / "messages.json"
    messages_path.write_text('[{"id":"i","channel":"c","text":"x","posted_at":123}]')
    if kind == "config":
        messages_path.write_text('[{"id":"i","channel":"c","text":"x","posted_at":"2026-11-01T09:00:00+00:00"}]')
    run = subprocess.run([sys.executable, "-m", "telegram_monitor.cli", "check", "--config",
                          str(config_path), "--messages", str(messages_path)], cwd=ROOT,
                         env={**__import__("os").environ, "PYTHONPATH": "src"}, capture_output=True, text=True)
    assert run.returncode == 2 and "error:" in run.stderr and "Traceback" not in run.stderr


def test_demo_determinism_matches_committed():
    outputs = []
    for _ in range(2):
        path = ROOT / "out" / "recreated.md"
        path.parent.mkdir(exist_ok=True)
        subprocess.run([sys.executable, "examples/run_demo.py", "--out", str(path)], cwd=ROOT, check=True)
        outputs.append(path.read_bytes())
    assert outputs[0] == outputs[1] == (ROOT / "examples/demo_report.md").read_bytes()


def test_package_data_copies_match_examples():
    examples = ROOT / "examples"
    if not examples.is_dir():
        pytest.skip("examples directory is absent")
    data = ROOT / "src/telegram_monitor/data"
    for name in ("config.example.json", "messages.example.json"):
        assert (data / name).read_bytes() == (examples / name).read_bytes()
