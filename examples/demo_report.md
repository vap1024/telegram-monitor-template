# Monitor demo report

## Summary

Run date: 2026-11-09T09:06:00+00:00

Total: 8
Alert: 3
Store: 2
Dropped duplicate: 2
Dropped muted: 1

## Alerts

- m01 | example-news | launch | 2.00 | Launch update: mainnet release is ready
- m07 | example-alerts | launch | 2.00 | Launch update: mainnet release is ready
- m08 | example-alerts | risk | 3.00 | Audit found an incident; response is ready

## Stored

- m03 | example-alerts | A short note about a review
- m06 | example-news | A launch note for later

## Dropped duplicates

- m02 | example-news | Launch update: mainnet release is ready
- m04 | example-chat | More context for the same report

## Dropped muted

- m05 | example-chat | digest | Weekly digest roundup

## Method notes

Rules are transparent; each fired rule contributes its weight once.
Text and shared-link keys expire at the configured time window.
Muted categories are evaluated after scoring. Alerts are emitted through a sink.
