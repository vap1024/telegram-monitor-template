"""Deterministic Markdown report rendering."""

from .pipeline import PipelineResult


def render_report(result: PipelineResult, now_iso: str) -> str:
    """Render fixed-order sections using only the provided timestamp and result."""
    lines = ["# Monitor demo report", "", "## Summary", "", f"Run date: {now_iso}", "",
             f"Total: {result.counts['total']}", f"Alert: {result.counts['alert']}",
             f"Store: {result.counts['store']}", f"Dropped duplicate: {result.counts['drop_duplicate']}",
             f"Dropped muted: {result.counts['drop_muted']}", "", "## Alerts", ""]
    for item in result.processed:
        if item.action == "alert":
            lines.append(f"- {item.message.id} | {item.message.channel} | {item.classification.category} | "
                         f"{item.classification.score:.2f} | {item.message.text[:80]}")
    lines.extend(["", "## Stored", ""])
    lines.extend(f"- {item.message.id} | {item.message.channel} | {item.message.text[:80]}"
                 for item in result.processed if item.action == "store")
    lines.extend(["", "## Dropped duplicates", ""])
    lines.extend(f"- {item.message.id} | {item.message.channel} | {item.message.text[:80]}"
                 for item in result.processed if item.action == "drop_duplicate")
    lines.extend(["", "## Dropped muted", ""])
    lines.extend(f"- {item.message.id} | {item.message.channel} | {item.classification.category} | "
                 f"{item.message.text[:80]}" for item in result.processed if item.action == "drop_muted")
    lines.extend(["", "## Method notes", "", "Rules are transparent; each fired rule contributes its weight once.",
                  "Text and shared-link keys expire at the configured time window.",
                  "Muted categories are evaluated after scoring. Alerts are emitted through a sink.", ""])
    return "\n".join(lines)
