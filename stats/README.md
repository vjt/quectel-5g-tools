# stats — quectel-5g-tools availability reporter

Stdlib-only Python tool that queries a VictoriaMetrics endpoint for the
series produced by `lua/prometheus-collectors/quectel*.lua` and emits a
markdown summary of:

- NR-attached fraction (watchdog gauge, ground truth)
- Detach episodes and max drop
- Carrier-aggregation depth distribution
- Signal quality medians (n78 RSRP/SINR, PCC RSRP)
- Watchdog action counter deltas per recovery stage

Designed to be re-run on a fixed cadence so successive windows are
directly comparable — same queries, same denominators, same format.

## Requirements

- Python 3.11+ (uses `tomllib`)
- Read access to a VictoriaMetrics or Prometheus-compatible
  `/api/v1/query_range` endpoint scraping the quectel-5g-tools series.

## Configuration

Default config path: `~/.config/quectel-5g-tools/config.toml`.

```toml
[stats]
vm_url = "https://metrics.example.com"
instance = "router1"
step = 60
```

CLI flags (`--vm-url`, `--instance`, `--step`) override config values.
A different config file can be selected with `--config /path/to.toml`.

## Usage

```sh
# Last 7 days
./nr-stats.py --window 7d

# Explicit window
./nr-stats.py --start 2026-05-13 --end 2026-06-12

# One-shot without a config file
./nr-stats.py --vm-url https://metrics.example.com --instance router1 --window 30d
```

## Series consumed

| Series | Source |
|---|---|
| `quectel_watchdog_nr_attached` | `quectel-watchdog.lua` |
| `quectel_watchdog_nr_carriers` | `quectel-watchdog.lua` |
| `quectel_watchdog_lte_carriers` | `quectel-watchdog.lua` |
| `quectel_watchdog_actions_total{stage}` | `quectel-watchdog.lua` |
| `modem_signal_rsrp_dbm{band, role}` | `quectel.lua` |
| `modem_signal_sinr_db{band}` | `quectel.lua` |

## Denominator note

`count()` over an instant-query returns no series when nothing matches
at that timestamp, so empty buckets are absent from the result. This
tool uses `window_seconds / step` as the denominator and treats missing
gauge buckets as detached — a watchdog that stopped emitting is itself
a degraded signal.

## Chunking

VictoriaMetrics rejects `/query_range` responses over 30 k points. The
tool chunks long windows into 14-day requests at 60 s step (configurable
via `CHUNK_SECONDS` in the source).
