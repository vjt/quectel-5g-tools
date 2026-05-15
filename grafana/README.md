# Grafana dashboard generator

`generate.py` builds the Quectel 5G / ISP Monitor dashboard JSON from
code so the layout, queries and thresholds stay in one place and the
JSON published to grafana.com (id `24835`) is reproducible.

Layout: three rows.

- **Connectivity** — ping current / availability / DNS for a configurable
  upstream target set (default: `1.1.1.1`, `8.8.8.8`, `facebook.com`,
  `reddit.com`, `google.com`, `sindro.me`).
- **Radio** — `modem_*` series from `lua/prometheus-collectors/quectel.lua`:
  Connected bands table, EnodeB / PCI / Freq, Band Status state-timeline,
  per-RAT SINR / RSRP / RSRQ.
- **Watchdog** — `quectel_watchdog_*` series from
  `lua/prometheus-collectors/quectel-watchdog.lua`: NR-attached
  current + 24 h %, CA depth, consecutive failed cycles, last recovery
  duration, state-file freshness, NR-attached time series, recovery
  actions per day by stage.

## Setup

No dependencies — Python 3 stdlib only (`grafanalib` was tried and
abandoned; it emits panel JSON that Grafana 11 silently truncates).

## Generate

```bash
# default: writes quectel-5g-monitor.json with a ${DS_VICTORIAMETRICS}
# datasource input placeholder (ready to upload to grafana.com or
# import into any Grafana instance).
python3 generate.py

# stream to stdout instead.
python3 generate.py --stdout

# bind to an explicit datasource uid (skip the import prompt — only
# useful when you know the target instance):
python3 generate.py --datasource-uid <uid>
```

The output is a top-level dashboard JSON (no `{"dashboard": ...,
"meta": ...}` wrapper). Import it via Grafana's UI ("Import" → upload
file) or push it to grafana.com.

## Push directly to a Grafana instance

```bash
export GRAFANA_URL=https://grafana.example
export GRAFANA_TOKEN=glsa_xxx        # or pass --token / --token-file

python3 generate.py --push
# resolved datasource uid <uid> from https://grafana.example
# pushed: uid=quectel-5g-monitor version=N → https://grafana.example/d/...
```

`--push` POSTs to `/api/dashboards/db`. If `--datasource-uid` isn't
explicit, the script queries `/api/datasources`, picks the first
`victoriametrics-metrics-datasource`, and bakes that uid in before
uploading. Pass `--no-overwrite` to fail on existing-uid collisions
instead of bumping the version.

`--push` deliberately does not also overwrite
`quectel-5g-monitor.json` — the bound-uid copy isn't what should be
checked in. To refresh the checked-in JSON, run `generate.py` (or
`generate.py --stdout > quectel-5g-monitor.json`) without `--push`.

## Data source assumptions

Datasource type: `victoriametrics-metrics-datasource`. Prometheus also
works but you may need to swap the type in the generated JSON before
importing — VictoriaMetrics-specific query options (e.g. `qryType` on
template variables) are tolerated by Prometheus but unused.

Metric sources expected:

| Metric prefix          | Producer                                       |
|------------------------|------------------------------------------------|
| `ping_*`               | telegraf `ping` plugin                         |
| `dns_query_*`          | telegraf `dns_query` plugin                    |
| `modem_*`              | `lua/prometheus-collectors/quectel.lua`        |
| `quectel_watchdog_*`   | `lua/prometheus-collectors/quectel-watchdog.lua` |

Template variables:

- `$router` — `label_values(ping_average_response_ms, host)` (multi).
- `$target` — `label_values(ping_average_response_ms, url)`.
