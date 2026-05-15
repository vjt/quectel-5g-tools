#!/usr/bin/env python3
"""Render a NR-attached / CA-depth / signal-quality summary from VictoriaMetrics.

Queries the watchdog and signal series produced by quectel-5g-tools and emits a
markdown report suitable for pasting into an availability journal. Stdlib only.

Configuration is read from ~/.config/quectel-5g-tools/config.toml (override
with --config). CLI flags take precedence. Example config:

    [stats]
    vm_url = "https://metrics.example.com"
    instance = "router1"
    step = 60

Usage:
    nr-stats.py --window 7d
    nr-stats.py --start 2026-05-13 --end 2026-06-12
    nr-stats.py --vm-url https://metrics.example.com --instance router1 --window 30d
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import tomllib
import urllib.parse
import urllib.request
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

CHUNK_SECONDS = 14 * 86400  # stays well under VM's 30k-point cap at step=60s
DEFAULT_CONFIG = Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config"))) \
    / "quectel-5g-tools" / "config.toml"


# ---------------- VM client ----------------

def vm_query_range(vm_url: str, query: str, start: float, end: float, step: int) -> list[tuple[float, float]]:
    """Query VM /api/v1/query_range, auto-chunked. Returns [(ts, val)] sorted."""
    samples: list[tuple[float, float]] = []
    cur = start
    while cur < end:
        chunk_end = min(cur + CHUNK_SECONDS, end)
        params = {
            "query": query,
            "start": f"{cur:.0f}",
            "end": f"{chunk_end:.0f}",
            "step": f"{step}s",
        }
        url = f"{vm_url.rstrip('/')}/api/v1/query_range?" + urllib.parse.urlencode(params)
        with urllib.request.urlopen(url, timeout=30) as resp:
            doc = json.loads(resp.read())
        if doc.get("status") != "success":
            raise RuntimeError(f"VM error for {query!r}: {doc}")
        for series in doc["data"]["result"]:
            for ts, val in series["values"]:
                if val in ("NaN", "+Inf", "-Inf"):
                    continue
                samples.append((float(ts), float(val)))
        cur = chunk_end
    seen: dict[float, float] = {}
    for ts, val in samples:
        seen[ts] = val
    return sorted(seen.items())


# ---------------- analysis ----------------

@dataclass
class NRAvail:
    expected_bins: int
    attached_bins: int
    detached_bins: int
    missing_bins: int
    episodes: list[tuple[float, int]]

    @property
    def pct_attached(self) -> float:
        return 100.0 * self.attached_bins / self.expected_bins if self.expected_bins else 0.0

    @property
    def max_drop_seconds(self) -> int:
        return max((d for _, d in self.episodes), default=0)

    @property
    def total_drop_seconds(self) -> int:
        return sum(d for _, d in self.episodes)


def analyse_attached(samples: list[tuple[float, float]], start: float, end: float, step: int) -> NRAvail:
    """Use the watchdog gauge to compute NR-attached fraction + drop episodes.

    Missing buckets are counted as detached: a gauge gap is itself a degraded
    signal — the watchdog stopped emitting or telegraf stopped scraping.
    """
    by_ts = {round((ts - start) / step): val for ts, val in samples}
    expected_bins = int((end - start) // step)
    attached = detached = missing = 0
    episodes: list[tuple[float, int]] = []
    cur_run_start: float | None = None
    cur_run_len = 0
    for i in range(expected_bins):
        if i in by_ts:
            v = by_ts[i]
            if v >= 0.5:
                attached += 1
                if cur_run_start is not None:
                    episodes.append((cur_run_start, cur_run_len * step))
                    cur_run_start, cur_run_len = None, 0
            else:
                detached += 1
                if cur_run_start is None:
                    cur_run_start = start + i * step
                cur_run_len += 1
        else:
            missing += 1
            if cur_run_start is None:
                cur_run_start = start + i * step
            cur_run_len += 1
    if cur_run_start is not None:
        episodes.append((cur_run_start, cur_run_len * step))
    return NRAvail(expected_bins, attached, detached, missing, episodes)


def ca_distribution(samples: list[tuple[float, float]]) -> Counter:
    return Counter(int(round(v)) for _, v in samples)


def quantiles(values: list[float]) -> tuple[float, float, float]:
    if not values:
        return float("nan"), float("nan"), float("nan")
    s = sorted(values)
    q = statistics.quantiles(s, n=4) if len(s) >= 4 else [s[0], s[len(s)//2], s[-1]]
    return q[0], statistics.median(s), q[2]


# ---------------- rendering ----------------

def fmt_duration(seconds: int) -> str:
    if seconds <= 0:
        return "0"
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h}h{m:02d}m"
    if m:
        return f"{m}m{s:02d}s"
    return f"{s}s"


def render(args, nr: NRAvail, ca: Counter, sig: dict[str, list[float]], actions: dict[str, tuple[float, float]]) -> str:
    window_days = (args.end_ts - args.start_ts) / 86400
    lines: list[str] = []
    lines.append(f"# nr-stats {args.start_iso} → {args.end_iso} ({window_days:.1f} d, instance={args.instance})")
    lines.append("")

    lines.append("## Availability")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("|---|---|")
    lines.append(f"| NR attached | **{nr.pct_attached:.2f} %** ({nr.attached_bins}/{nr.expected_bins} bins @ {args.step}s) |")
    lines.append(f"| Detached bins | {nr.detached_bins} |")
    lines.append(f"| Missing bins (gauge gap → counted detached) | {nr.missing_bins} |")
    lines.append(f"| Detach episodes | {len(nr.episodes)} |")
    lines.append(f"| Max drop | {fmt_duration(nr.max_drop_seconds)} |")
    lines.append(f"| Total down | {fmt_duration(nr.total_drop_seconds)} |")
    lines.append("")
    long_episodes = [(ts, dur) for ts, dur in nr.episodes if dur >= 120]
    if long_episodes:
        lines.append("Episodes ≥ 2 min (UTC):")
        lines.append("")
        lines.append("| Start | Duration |")
        lines.append("|---|---|")
        for ts, dur in long_episodes:
            lines.append(f"| {datetime.fromtimestamp(ts, tz=timezone.utc):%Y-%m-%d %H:%M} | {fmt_duration(dur)} |")
        lines.append("")

    total_ca = sum(ca.values())
    lines.append("## CA depth distribution")
    lines.append("")
    lines.append("| Total carriers | Bins | % |")
    lines.append("|---|---|---|")
    for n in sorted(ca):
        pct = 100.0 * ca[n] / total_ca if total_ca else 0.0
        lines.append(f"| {n} | {ca[n]} | {pct:.2f} |")
    lines.append("")
    if total_ca:
        lines.append(f"Max observed: **{max(ca)}** carriers. Sample count: {total_ca} bins.")
        lines.append("")

    lines.append("## Signal quality")
    lines.append("")
    lines.append("| Series | p25 | median | p75 | samples |")
    lines.append("|---|---|---|---|---|")
    for label, vals in sig.items():
        p25, med, p75 = quantiles(vals)
        lines.append(f"| {label} | {p25:.1f} | **{med:.1f}** | {p75:.1f} | {len(vals)} |")
    lines.append("")

    lines.append("## Watchdog actions over window")
    lines.append("")
    lines.append("| Stage | Δ count |")
    lines.append("|---|---|")
    for stage, (a, b) in sorted(actions.items()):
        delta = max(0, int(round(b - a)))
        lines.append(f"| {stage} | {delta} |")
    lines.append("")

    return "\n".join(lines)


# ---------------- queries ----------------

def collect(args) -> str:
    inst = args.instance
    vm = args.vm_url
    start, end, step = args.start_ts, args.end_ts, args.step

    nr_samples = vm_query_range(
        vm, f'quectel_watchdog_nr_attached{{instance="{inst}"}}', start, end, step)
    nr = analyse_attached(nr_samples, start, end, step)

    ca_samples = vm_query_range(
        vm,
        f'quectel_watchdog_nr_carriers{{instance="{inst}"}} '
        f'+ quectel_watchdog_lte_carriers{{instance="{inst}"}}',
        start, end, step)
    ca = ca_distribution(ca_samples)

    sig: dict[str, list[float]] = {}
    for label, query in [
        ("n78 RSRP dBm",    f'modem_signal_rsrp_dbm{{instance="{inst}",band="n78"}}'),
        ("n78 SINR dB",     f'modem_signal_sinr_db{{instance="{inst}",band="n78"}}'),
        ("PCC RSRP dBm",    f'modem_signal_rsrp_dbm{{instance="{inst}",role="pcc"}}'),
    ]:
        samples = vm_query_range(vm, query, start, end, step)
        sig[label] = [v for _, v in samples]

    actions: dict[str, tuple[float, float]] = {}
    for stage in ("mode_toggle", "bearer_reconnect"):
        samples = vm_query_range(
            vm,
            f'quectel_watchdog_actions_total{{instance="{inst}",stage="{stage}"}}',
            start, end, step)
        actions[stage] = (samples[0][1], samples[-1][1]) if samples else (0.0, 0.0)

    return render(args, nr, ca, sig, actions)


# ---------------- config + CLI ----------------

def load_config(path: Path) -> dict:
    if not path.exists():
        return {}
    with path.open("rb") as f:
        doc = tomllib.load(f)
    return doc.get("stats", {})


def parse_iso(s: str) -> datetime:
    if "T" in s:
        return datetime.fromisoformat(s).replace(tzinfo=timezone.utc)
    return datetime.strptime(s, "%Y-%m-%d").replace(tzinfo=timezone.utc)


def parse_window(s: str) -> timedelta:
    n = int(s[:-1])
    u = s[-1]
    if u == "d":
        return timedelta(days=n)
    if u == "h":
        return timedelta(hours=n)
    raise ValueError(f"bad window {s!r}")


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__.splitlines()[0],
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"Default config path: {DEFAULT_CONFIG}",
    )
    ap.add_argument("--config", type=Path, default=DEFAULT_CONFIG, help="Path to config.toml")
    ap.add_argument("--vm-url", help="VictoriaMetrics base URL (overrides config)")
    ap.add_argument("--instance", help="Prometheus instance label (overrides config)")
    ap.add_argument("--start", help="ISO date or datetime, UTC")
    ap.add_argument("--end", help="ISO date or datetime, UTC (default: now)")
    ap.add_argument("--window", help="Relative window, e.g. 7d, 30d (overrides --start)")
    ap.add_argument("--step", type=int, help="Query step seconds (default 60)")
    args = ap.parse_args(argv)

    cfg = load_config(args.config)
    args.vm_url = args.vm_url or cfg.get("vm_url")
    args.instance = args.instance or cfg.get("instance")
    args.step = args.step or cfg.get("step", 60)

    if not args.vm_url:
        ap.error(f"vm_url not set (CLI --vm-url or {args.config} [stats] vm_url)")
    if not args.instance:
        ap.error(f"instance not set (CLI --instance or {args.config} [stats] instance)")

    end_dt = parse_iso(args.end) if args.end else datetime.now(tz=timezone.utc)
    if args.window:
        start_dt = end_dt - parse_window(args.window)
    elif args.start:
        start_dt = parse_iso(args.start)
    else:
        ap.error("provide --start or --window")
    if start_dt >= end_dt:
        ap.error("start must precede end")

    args.start_ts = start_dt.timestamp()
    args.end_ts = end_dt.timestamp()
    args.start_iso = start_dt.strftime("%Y-%m-%d %H:%M")
    args.end_iso = end_dt.strftime("%Y-%m-%d %H:%M")

    print(collect(args))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
