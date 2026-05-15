#!/usr/bin/env python3
"""Generate the Quectel 5G / ISP Monitor Grafana dashboard.

Built by re-templating the upstream "Ultimate ISP & 5G/LTE Monitor"
dashboard (grafana.com id 24835, snapshot in `_source-dashboard.json`):
every panel here is a verbatim clone of an upstream panel, with only
`gridPos`, `datasource`, and the panel-id rewritten. Layout reorganized
into three rows (Connectivity / Radio / Watchdog) and a Watchdog row
appended with quectel-5g-tools watchdog metrics.
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


DS_PLUGIN_ID = "victoriametrics-metrics-datasource"
DS_PLUGIN_NAME = "VictoriaMetrics"
DEFAULT_DS_INPUT = "${DS_VICTORIAMETRICS}"

SOURCE_SNAPSHOT = Path(__file__).resolve().parent / "_source-dashboard.json"


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def gp(x: int, y: int, w: int, h: int) -> dict:
    return {"h": h, "w": w, "x": x, "y": y}


def ds(uid: str) -> dict:
    return {"type": DS_PLUGIN_ID, "uid": uid}


def steps(*pairs) -> dict:
    """`pairs` is (color, value) tuples in ascending order; first value is null."""
    out = []
    for i, (color, value) in enumerate(pairs):
        step = {"color": color, "value": None if i == 0 else value}
        out.append(step)
    return {"mode": "absolute", "steps": out}


# ---------------------------------------------------------------------------
# source dashboard loader
# ---------------------------------------------------------------------------

def load_source() -> dict[int, dict]:
    """Return {source_panel_id: panel_dict} from the saved snapshot."""
    raw = json.loads(SOURCE_SNAPSHOT.read_text())
    return {p["id"]: p for p in raw["dashboard"]["panels"]}


def clone(src: dict, **overrides) -> dict:
    """Deep-copy a source panel and apply overrides.

    Supported overrides:
      - gridPos: dict (replace entirely)
      - expr: str (set targets[0].expr+query; for single-target panels)
      - exprs: list[str] (set per-target expr by index, len must match)
      - title: str
      - id: int
    Any other kwarg replaces the matching top-level field verbatim.
    """
    p = copy.deepcopy(src)
    if "gridPos" in overrides:
        p["gridPos"] = overrides.pop("gridPos")
    if "id" in overrides:
        p["id"] = overrides.pop("id")
    if "title" in overrides:
        p["title"] = overrides.pop("title")
    if "expr" in overrides:
        e = overrides.pop("expr")
        for t in p.get("targets", []):
            t["expr"] = e
            break
    if "exprs" in overrides:
        es = overrides.pop("exprs")
        for t, e in zip(p["targets"], es):
            t["expr"] = e
    for k, v in overrides.items():
        p[k] = v
    return p


# ---------------------------------------------------------------------------
# layout — Connectivity / Radio + Watchdog
# ---------------------------------------------------------------------------

def build_panels(src: dict[int, dict]) -> list:
    panels: list = []

    # ── Radio ───────────────────────────────────────────────────────────
    panels.append(
        {"type": "row", "title": "Radio", "collapsed": False, "panels": [],
         "gridPos": gp(0, 0, 24, 1)}
    )
    panels.append(clone(src[38], gridPos=gp(0, 1, 11, 7)))      # Connected bands

    # EnodeB: join modem_operator_info to bring MCC/MNC labels into the
    # frame so the LTEItaly data link can derive the network code from
    # data instead of hardcoding `2221` (TIM IT).
    enodeb = clone(src[39], gridPos=gp(11, 1, 7, 7))
    for t in enodeb["targets"]:
        t["expr"] = (
            'modem_cell_state{role="pcc"}'
            ' * on() group_left(mcc, mnc) modem_operator_info == 1'
        )
    for link in enodeb["fieldConfig"]["defaults"].get("links", []):
        if "lteitaly.it" in link.get("url", ""):
            link["url"] = (
                'https://lteitaly.it/internal/map.php'
                '#bts=${__data.fields["mcc"]}${__data.fields["mnc"]}'
                '.${__value.text}'
            )
    panels.append(enodeb)
    panels.append(clone(src[46], gridPos=gp(18, 1, 3, 4)))      # 4G PCI
    panels.append(clone(src[47], gridPos=gp(21, 1, 3, 4)))      # 5G PCI
    panels.append(clone(src[48], gridPos=gp(18, 5, 3, 3)))      # 4G Freq
    panels.append(clone(src[49], gridPos=gp(21, 5, 3, 3)))      # 5G Freq

    panels.append(clone(src[34], gridPos=gp(0, 8, 13, 8)))      # Band status
    panels.append(clone(src[40], gridPos=gp(13, 8, 2, 4)))      # 4G Band
    panels.append(clone(src[42], gridPos=gp(15, 8, 3, 4)))      # 4G SINR
    panels.append(clone(src[44], gridPos=gp(18, 8, 3, 4)))      # 4G RSRP
    panels.append(clone(src[50], gridPos=gp(21, 8, 3, 4)))      # 4G RSRQ
    panels.append(clone(src[41], gridPos=gp(13, 12, 2, 4)))     # 5G Band
    panels.append(clone(src[43], gridPos=gp(15, 12, 3, 4)))     # 5G SINR
    panels.append(clone(src[45], gridPos=gp(18, 12, 3, 4)))     # 5G RSRP
    panels.append(clone(src[51], gridPos=gp(21, 12, 3, 4)))     # 5G RSRQ

    panels.append(clone(src[35], gridPos=gp(0, 16, 24, 8)))     # SINR ts
    panels.append(clone(src[36], gridPos=gp(0, 24, 24, 8)))     # RSRP ts
    panels.append(clone(src[37], gridPos=gp(0, 32, 24, 8)))     # RSRQ ts

    # ── Connectivity ────────────────────────────────────────────────────
    panels.append(
        {"type": "row", "title": "Connectivity", "collapsed": False, "panels": [],
         "gridPos": gp(0, 40, 24, 1)}
    )
    # ping current stats (source ids: 4 7 8 9 32 31)
    for i, sid in enumerate([4, 7, 8, 9, 32, 31]):
        p = clone(src[sid], gridPos=gp(i * 4, 41, 4, 5))
        if sid == 31:
            # Upstream dashboard has a copy-paste bug: the sindro.me ping
            # current stat queries `url="8.8.8.8"`. Fix here.
            for t in p["targets"]:
                t["expr"] = 'ping_average_response_ms{url="sindro.me", host=~"$router"}'
        panels.append(p)
    # $target ping metrics
    panels.append(clone(src[13], gridPos=gp(0, 46, 24, 10)))
    # Avg Response Time / Packet Loss %
    panels.append(clone(src[14], gridPos=gp(0, 56, 12, 8)))
    panels.append(clone(src[15], gridPos=gp(12, 56, 12, 8)))
    # availability stats (1.1.1.1 8.8.8.8 facebook reddit google sindro = 20 19 24 21 23 22)
    for i, sid in enumerate([20, 19, 24, 21, 23, 22]):
        panels.append(clone(src[sid], gridPos=gp(i * 4, 64, 4, 6)))
    # DNS Response Time
    panels.append(clone(src[30], gridPos=gp(0, 70, 24, 7)))

    # ── Watchdog ────────────────────────────────────────────────────────
    panels.append(
        {"type": "row", "title": "Watchdog (NR babysit)", "collapsed": False,
         "panels": [], "gridPos": gp(0, 77, 24, 1)}
    )
    # Build watchdog stats by cloning the EnodeB stat (id 39) — same Stat
    # shape, swap title/expr/fields/threshold/colorMode.
    stat_tpl = src[39]
    ts_tpl = src[35]

    def wd_stat(*, title, expr, x, y, w=4, h=4, unit=None, color_mode="value",
                graph_mode="area", text_mode="auto", thresholds=None,
                mappings=None, decimals=None, fields="", reduce_calcs=None,
                links=None, min_=None, max_=None):
        p = copy.deepcopy(stat_tpl)
        p["title"] = title
        p["gridPos"] = gp(x, y, w, h)
        p["targets"] = [
            {
                "datasource": ds(DEFAULT_DS_INPUT),
                "editorMode": "code",
                "exemplar": False,
                "expr": expr,
                "format": "time_series",
                "instant": False,
                "interval": "",
                "legendFormat": "{{instance}}",
                "range": True,
                "refId": "A",
            }
        ]
        defs = p["fieldConfig"]["defaults"]
        defs["thresholds"] = thresholds or steps(("green", 0))
        defs["mappings"] = mappings or []
        defs.pop("links", None)
        if links:
            defs["links"] = links
        if unit is not None:
            defs["unit"] = unit
        else:
            defs.pop("unit", None)
        if decimals is not None:
            defs["decimals"] = decimals
        else:
            defs.pop("decimals", None)
        if min_ is not None:
            defs["min"] = min_
        if max_ is not None:
            defs["max"] = max_
        opts = p["options"]
        opts["colorMode"] = color_mode
        opts["graphMode"] = graph_mode
        opts["textMode"] = text_mode
        opts["reduceOptions"] = {
            "calcs": reduce_calcs or ["lastNotNull"],
            "fields": fields,
            "values": False,
        }
        return p

    def wd_ts(*, title, expr, x, y, w=12, h=8, unit="short",
              thresholds=None, fill_opacity=10, draw_style="line",
              legend_calcs=None, legend_mode="list", value_min=None,
              value_max=None, line_interpolation="linear"):
        p = copy.deepcopy(ts_tpl)
        p["title"] = title
        p["gridPos"] = gp(x, y, w, h)
        p["targets"] = [
            {
                "datasource": ds(DEFAULT_DS_INPUT),
                "editorMode": "code",
                "exemplar": False,
                "expr": expr,
                "format": "time_series",
                "legendFormat": "{{instance}}",
                "range": True,
                "refId": "A",
            }
        ]
        defs = p["fieldConfig"]["defaults"]
        defs["unit"] = unit
        defs["thresholds"] = thresholds or steps(("green", 0))
        defs["custom"]["fillOpacity"] = fill_opacity
        defs["custom"]["drawStyle"] = draw_style
        defs["custom"]["lineInterpolation"] = line_interpolation
        defs["mappings"] = []
        if value_min is not None:
            defs["min"] = value_min
        if value_max is not None:
            defs["max"] = value_max
        # Strip per-RAT overrides from the cloned signal-ts template;
        # watchdog series have no technology/role/band axis.
        p["fieldConfig"]["overrides"] = []
        opts = p["options"]
        opts["legend"]["calcs"] = legend_calcs or ["lastNotNull", "mean"]
        opts["legend"]["displayMode"] = legend_mode
        return p

    panels.append(wd_stat(
        title="NR attached", x=0, y=78,
        expr='quectel_watchdog_nr_attached{instance=~"$router"}',
        color_mode="background", graph_mode="none", text_mode="auto",
        thresholds=steps(("red", 0), ("green", 1)),
        mappings=[
            {
                "type": "value",
                "options": {
                    "0": {"color": "red", "index": 0, "text": "DETACHED"},
                    "1": {"color": "green", "index": 1, "text": "5G NR"},
                },
            }
        ],
    ))
    panels.append(wd_stat(
        title="NR attached % (24h)", x=4, y=78,
        expr='100 * avg_over_time(quectel_watchdog_nr_attached{instance=~"$router"}[24h])',
        unit="percent", decimals=2, color_mode="background",
        thresholds=steps(("red", 0), ("orange", 95), ("yellow", 99), ("green", 99.9)),
        min_=0, max_=100,
    ))
    panels.append(wd_stat(
        title="CA depth", x=8, y=78,
        expr='quectel_watchdog_nr_carriers{instance=~"$router"}'
             ' + quectel_watchdog_lte_carriers{instance=~"$router"}',
        thresholds=steps(("red", 0), ("yellow", 2), ("green", 3)),
    ))
    panels.append(wd_stat(
        title="Failed cycles in a row", x=12, y=78,
        expr='quectel_watchdog_consecutive_failed_actions{instance=~"$router"}',
        color_mode="background", graph_mode="none",
        thresholds=steps(("green", 0), ("yellow", 1), ("orange", 2), ("red", 3)),
    ))
    panels.append(wd_stat(
        title="Last recovery duration", x=16, y=78,
        expr='quectel_watchdog_last_recovery_duration_seconds{instance=~"$router"}',
        unit="s",
        thresholds=steps(("green", 0), ("yellow", 120), ("orange", 240), ("red", 360)),
    ))
    panels.append(wd_stat(
        title="State age", x=20, y=78,
        expr='time() - quectel_watchdog_updated_timestamp_seconds{instance=~"$router"}',
        unit="s", color_mode="background", graph_mode="none",
        thresholds=steps(("green", 0), ("yellow", 180), ("red", 300)),
    ))
    panels.append(wd_ts(
        title="NR attached", x=0, y=82,
        expr='quectel_watchdog_nr_attached{instance=~"$router"}',
        unit="short",
        thresholds=steps(("red", 0), ("green", 1)),
        fill_opacity=20, value_min=0, value_max=1,
        legend_calcs=["lastNotNull", "mean"],
    ))
    panels.append(wd_ts(
        title="Recovery actions (per day)", x=12, y=82,
        expr='sum by (stage) (increase(quectel_watchdog_actions_total{instance=~"$router"}[1d]))',
        unit="short",
        thresholds=steps(("green", 0)),
        fill_opacity=30, draw_style="bars",
        legend_calcs=["lastNotNull", "sum"],
        legend_mode="table",
    ))
    # Override legendFormat for actions ts (stage label, not instance).
    panels[-1]["targets"][0]["legendFormat"] = "{{stage}}"

    return panels


# ---------------------------------------------------------------------------
# templating (variables)
# ---------------------------------------------------------------------------

def templating(ds_uid: str) -> dict:
    base_ds = ds(ds_uid)
    return {
        "list": [
            {
                "name": "router",
                "label": "router",
                "type": "query",
                "datasource": base_ds,
                "definition": "label_values(ping_average_response_ms,host)",
                "query": {
                    "qryType": 1,
                    "query": "label_values(ping_average_response_ms,host)",
                    "refId": "VariableQueryEditor-VariableQuery",
                },
                "refresh": 1,
                "sort": 1,
                "multi": True,
                "includeAll": True,
                "allValue": ".+",
                "options": [],
                "current": {"text": ["All"], "value": ["$__all"]},
                "regex": "",
            },
            {
                "name": "target",
                "label": "ping target",
                "type": "query",
                "datasource": base_ds,
                "definition": "label_values(ping_average_response_ms,url)",
                "query": {
                    "qryType": 1,
                    "query": "label_values(ping_average_response_ms,url)",
                    "refId": "VariableQueryEditor-VariableQuery",
                },
                "refresh": 1,
                "sort": 1,
                "multi": False,
                "includeAll": False,
                "options": [],
                "current": {"text": "sindro.me", "value": "sindro.me"},
                "regex": "",
            },
        ]
    }


# ---------------------------------------------------------------------------
# dashboard build
# ---------------------------------------------------------------------------

def build_dashboard(ds_uid: str, include_inputs: bool) -> dict:
    src = load_source()
    panels = build_panels(src)
    _assign_panel_ids(panels)
    _patch_panel_datasources(panels, ds_uid)
    dash: dict = {
        "title": "Quectel 5G / ISP Monitor (RM520N-GL)",
        "description": (
            "ISP upstream health + Quectel RM520N-GL radio state + 5g-watchdog. "
            "Generated by quectel-5g-tools/grafana/generate.py."
        ),
        "uid": "quectel-5g-monitor",
        "tags": ["5g", "lte", "quectel", "openwrt"],
        "timezone": "browser",
        "refresh": "1m",
        "schemaVersion": 42,
        "panels": panels,
        "editable": True,
        "templating": templating(ds_uid),
        "time": {"from": "now-6h", "to": "now"},
        "annotations": {
            "list": [
                {
                    "builtIn": 1,
                    "datasource": {"type": "grafana", "uid": "-- Grafana --"},
                    "enable": True,
                    "hide": True,
                    "iconColor": "rgba(0, 211, 255, 1)",
                    "name": "Annotations & Alerts",
                    "type": "dashboard",
                }
            ]
        },
        "links": [],
    }
    if include_inputs:
        dash["__inputs"] = [
            {
                "name": "DS_VICTORIAMETRICS",
                "label": DS_PLUGIN_NAME,
                "description": "",
                "type": "datasource",
                "pluginId": DS_PLUGIN_ID,
                "pluginName": DS_PLUGIN_NAME,
            }
        ]
        dash["__requires"] = [
            {"type": "grafana", "id": "grafana", "name": "Grafana", "version": "11.0.0"},
            {
                "type": "datasource",
                "id": DS_PLUGIN_ID,
                "name": DS_PLUGIN_NAME,
                "version": "1.0.0",
            },
        ]
    return dash


def _assign_panel_ids(panels: list, start: int = 1) -> int:
    next_id = start
    for panel in panels:
        if not isinstance(panel, dict):
            continue
        panel["id"] = next_id
        next_id += 1
        if panel.get("type") == "row":
            next_id = _assign_panel_ids(panel.get("panels", []) or [], next_id)
    return next_id


def _patch_panel_datasources(panels: list, ds_uid: str) -> None:
    ds_obj = ds(ds_uid)
    for panel in panels:
        if not isinstance(panel, dict):
            continue
        if panel.get("type") == "row":
            for sub in panel.get("panels", []) or []:
                _patch_panel_datasources([sub], ds_uid)
            continue
        panel["datasource"] = copy.deepcopy(ds_obj)
        for t in panel.get("targets", []) or []:
            t["datasource"] = copy.deepcopy(ds_obj)


# ---------------------------------------------------------------------------
# Grafana API client
# ---------------------------------------------------------------------------

def _api(url: str, token: str, path: str, data: dict | None = None) -> Any:
    req = urllib.request.Request(
        f"{url.rstrip('/')}{path}",
        data=json.dumps(data).encode() if data is not None else None,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST" if data is not None else "GET",
    )
    try:
        with urllib.request.urlopen(req) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise SystemExit(f"grafana API {path} → HTTP {e.code}: {body}") from e


def resolve_ds_uid(url: str, token: str) -> str:
    for d in _api(url, token, "/api/datasources"):
        if d.get("type") == DS_PLUGIN_ID:
            return d["uid"]
    raise SystemExit(
        f"no datasource of type {DS_PLUGIN_ID!r} on {url}; pass --datasource-uid"
    )


def push_dashboard(
    url: str,
    token: str,
    dash: dict,
    folder_uid: str = "",
    overwrite: bool = True,
    message: str = "",
) -> dict:
    body_dash = {k: v for k, v in dash.items() if not k.startswith("__")}
    body_dash["id"] = None
    return _api(
        url,
        token,
        "/api/dashboards/db",
        {
            "dashboard": body_dash,
            "folderUid": folder_uid,
            "overwrite": overwrite,
            "message": message,
        },
    )


def _load_token(token: str | None, token_file: str | None) -> str:
    if token:
        return token
    if token_file:
        return Path(token_file).read_text().strip()
    env = os.environ.get("GRAFANA_TOKEN")
    if env:
        return env
    raise SystemExit("--push needs --token, --token-file, or $GRAFANA_TOKEN")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    here = Path(__file__).resolve().parent
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument(
        "--datasource-uid",
        default=DEFAULT_DS_INPUT,
        help=(
            "Datasource uid. Default uses the dashboard-input placeholder "
            "`${DS_VICTORIAMETRICS}` so the file is import-friendly. "
            "Pass an explicit uid to bind to a known instance."
        ),
    )
    p.add_argument(
        "--output",
        default=str(here / "quectel-5g-monitor.json"),
        help="Output JSON path (default: %(default)s)",
    )
    p.add_argument("--stdout", action="store_true", help="Write to stdout instead of a file")

    push = p.add_argument_group(
        "push", "Upload the generated dashboard to a Grafana instance."
    )
    push.add_argument("--push", action="store_true", help="POST to /api/dashboards/db")
    push.add_argument(
        "--grafana-url",
        default=os.environ.get("GRAFANA_URL"),
        help="Grafana base URL (env: GRAFANA_URL)",
    )
    push.add_argument("--token", help="Grafana service-account token (env: GRAFANA_TOKEN)")
    push.add_argument(
        "--token-file", help="Path to a file containing the Grafana token"
    )
    push.add_argument(
        "--folder-uid", default="", help="Target folder uid (default: General)"
    )
    push.add_argument(
        "--message",
        default="generated by quectel-5g-tools/grafana/generate.py",
        help="Dashboard version message",
    )
    push.add_argument(
        "--no-overwrite",
        dest="overwrite",
        action="store_false",
        default=True,
        help="Fail if the target dashboard already exists at that uid",
    )

    args = p.parse_args()

    if args.push and args.datasource_uid == DEFAULT_DS_INPUT:
        if not args.grafana_url:
            raise SystemExit("--push needs --grafana-url (or $GRAFANA_URL)")
        token = _load_token(args.token, args.token_file)
        args.datasource_uid = resolve_ds_uid(args.grafana_url, token)
        print(
            f"resolved datasource uid {args.datasource_uid} from {args.grafana_url}",
            file=sys.stderr,
        )

    use_input = args.datasource_uid == DEFAULT_DS_INPUT
    dash = build_dashboard(args.datasource_uid, include_inputs=use_input)
    text = json.dumps(dash, indent=2, sort_keys=False) + "\n"

    if args.stdout:
        sys.stdout.write(text)
    elif not args.push:
        Path(args.output).write_text(text)
        print(f"wrote {args.output} ({len(text)} bytes)", file=sys.stderr)

    if args.push:
        if not args.grafana_url:
            raise SystemExit("--push needs --grafana-url (or $GRAFANA_URL)")
        token = _load_token(args.token, args.token_file)
        result = push_dashboard(
            args.grafana_url,
            token,
            dash,
            folder_uid=args.folder_uid,
            overwrite=args.overwrite,
            message=args.message,
        )
        dash_url = f"{args.grafana_url.rstrip('/')}{result.get('url', '')}"
        print(
            f"pushed: uid={result.get('uid')} version={result.get('version')} → {dash_url}",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
