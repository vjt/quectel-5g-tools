"""Configuration loading for quectel-5g-tools."""

import json
import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional


DEFAULT_CONFIG_PATHS = [
    "/etc/quectel/config.json",
    "~/.config/quectel/config.json",
    "./config/quectel.json",
]


@dataclass
class Config:
    """Configuration for quectel-5g-tools."""

    # Modem device path (None = auto-detect)
    modem_device: Optional[str] = None

    # gl_modem bus ID (for GL.INET devices)
    modem_bus: Optional[str] = None

    # Backend to use: "serial" or "gl_modem"
    backend: str = "gl_modem"

    # Refresh interval for monitoring (seconds)
    refresh_interval: float = 5.0

    # Interval between beeps (seconds)
    beep_interval: float = 0.6

    # LTE bands to lock to (empty = all)
    lte_bands: List[int] = field(default_factory=list)

    # NR5G bands to lock to (empty = all)
    nr5g_bands: List[int] = field(default_factory=list)

    # Serial port settings
    serial_baudrate: int = 115200
    serial_timeout: float = 2.0


def _try_uci_get(key: str) -> Optional[str]:
    """Try to get a value from UCI (OpenWRT config system)."""
    try:
        result = subprocess.run(
            ["uci", "get", f"quectel.@modem[0].{key}"],
            capture_output=True,
            text=True,
            timeout=2,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return None


def _is_openwrt() -> bool:
    """Check if running on OpenWRT."""
    return os.path.exists("/etc/openwrt_release")


def load_config(config_path: Optional[str] = None) -> Config:
    """Load configuration from JSON file, with UCI overlay on OpenWRT.

    Args:
        config_path: Explicit path to config file. If None, searches default paths.

    Returns:
        Config object with loaded settings.
    """
    config = Config()

    # Find config file
    paths_to_try = [config_path] if config_path else DEFAULT_CONFIG_PATHS

    config_data = {}
    for path in paths_to_try:
        if path is None:
            continue
        expanded = Path(path).expanduser()
        if expanded.exists():
            try:
                with open(expanded) as f:
                    config_data = json.load(f)
                break
            except (json.JSONDecodeError, IOError):
                continue

    # Apply JSON config
    if "modem_device" in config_data:
        config.modem_device = config_data["modem_device"]
    if "modem_bus" in config_data:
        config.modem_bus = config_data["modem_bus"]
    if "backend" in config_data:
        config.backend = config_data["backend"]
    if "refresh_interval" in config_data:
        config.refresh_interval = float(config_data["refresh_interval"])
    if "beep_interval" in config_data:
        config.beep_interval = float(config_data["beep_interval"])
    if "lte_bands" in config_data:
        config.lte_bands = list(config_data["lte_bands"])
    if "nr5g_bands" in config_data:
        config.nr5g_bands = list(config_data["nr5g_bands"])
    if "serial_baudrate" in config_data:
        config.serial_baudrate = int(config_data["serial_baudrate"])
    if "serial_timeout" in config_data:
        config.serial_timeout = float(config_data["serial_timeout"])

    # Overlay UCI config if on OpenWRT
    if _is_openwrt():
        uci_device = _try_uci_get("device")
        if uci_device:
            config.modem_device = uci_device

        uci_bus = _try_uci_get("bus")
        if uci_bus:
            config.modem_bus = uci_bus

        uci_backend = _try_uci_get("backend")
        if uci_backend:
            config.backend = uci_backend

        uci_refresh = _try_uci_get("refresh_interval")
        if uci_refresh:
            try:
                config.refresh_interval = float(uci_refresh)
            except ValueError:
                pass

        uci_beep = _try_uci_get("beep_interval")
        if uci_beep:
            try:
                config.beep_interval = float(uci_beep)
            except ValueError:
                pass

    # Set sensible defaults for GL.INET X3000 if no config found
    if config.modem_bus is None and config.backend == "gl_modem":
        config.modem_bus = "1-1.2"

    return config
