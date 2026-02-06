# Legacy Python Implementation

This directory contains the original Python implementation of quectel-5g-tools.

## Why We Switched to Lua

In February 2026, we decided to rewrite the entire project in Lua. Here's why:

### 1. OpenWRT is the Target Platform

This software is specifically designed for OpenWRT routers with Quectel modems. Lua is native to OpenWRT - it powers LuCI, UCI bindings, and the entire web interface. Python is a second-class citizen that requires additional packages.

### 2. Prometheus Exporter Required Lua Anyway

We wanted to add a Prometheus exporter for Grafana dashboards. The standard `prometheus-node-exporter-lua` on OpenWRT uses Lua collectors. Writing the exporter in Lua while keeping the core in Python would mean maintaining two implementations of the same parsing logic. That's a maintenance burden we didn't want.

### 3. Dependencies

The Python implementation required:
- `python3-pyserial` (~200KB)
- `python3-toml` (~50KB)
- `python3-ncurses` (~150KB)
- Python3 base (~2MB)

The Lua implementation requires:
- `luaposix` (~100KB) - for serial I/O and curses
- Lua is already present on OpenWRT

### 4. Performance

Lua starts faster and uses less memory. On resource-constrained routers, this matters.

### 5. Single Implementation

Having one codebase in Lua means:
- One place to fix bugs
- One set of tests
- One language to understand
- Easier contributions from OpenWRT developers who already know Lua

## What's Here

- `python/` - Complete Python implementation
  - `bin/` - CLI tools (5g-info, 5g-monitor, 5g-http.cgi, at, force-bands)
  - `src/quectel/` - Python library (parser, modem, frequency conversion, etc.)
  - `tests/` - pytest-based unit tests
  - `pyproject.toml` - Python package configuration
  - `5g-monitor-original.py` - The original prototype script
  - `5g-scan-original.py` - The original scan script

## Can I Still Use This?

Yes. The Python code works fine. If you're on a non-OpenWRT system with Python available, you can:

```bash
cd legacy/python
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

But it won't receive updates. The Lua implementation in the parent directory is the maintained version.
