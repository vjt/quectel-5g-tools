"""Configuration loading for quectel-5g-tools.

Configuration sources (in order of priority):
1. UCI (OpenWRT) - highest priority
2. TOML config file
3. Built-in defaults
"""

import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

try:
    import tomllib  # Python 3.11+
except ImportError:
    try:
        import tomli as tomllib  # Fallback for Python < 3.11
    except ImportError:
        tomllib = None  # TOML support not available


DEFAULT_CONFIG_PATHS = [
    "/etc/quectel/config.toml",
    "~/.config/quectel/config.toml",
    "./config/quectel.toml",
]

# UCI package and section
UCI_PACKAGE = "quectel"
UCI_SECTION = "modem"


@dataclass
class Config:
    """Configuration for quectel-5g-tools."""

    # [modem] section
    device: str = "/dev/ttyUSB2"
    baudrate: int = 115200
    timeout: float = 2.0

    # [monitor] section
    refresh_interval: float = 5.0
    beep_interval: float = 0.6
    beeps_enabled: bool = True

    # [bands] section
    lte_bands: List[int] = field(default_factory=list)
    nr5g_bands: List[int] = field(default_factory=list)


def _is_openwrt() -> bool:
    """Check if running on OpenWRT."""
    return os.path.exists("/etc/openwrt_release")


def _uci_get(key: str) -> Optional[str]:
    """Get a value from UCI.

    Args:
        key: UCI key (e.g., "device", "baudrate")

    Returns:
        Value as string, or None if not found/error
    """
    try:
        result = subprocess.run(
            ["uci", "-q", "get", f"{UCI_PACKAGE}.{UCI_SECTION}.{key}"],
            capture_output=True,
            text=True,
            timeout=2,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass
    return None


def _uci_get_list(key: str) -> Optional[List[str]]:
    """Get a list value from UCI.

    Args:
        key: UCI key for list option

    Returns:
        List of values, or None if not found/error
    """
    try:
        result = subprocess.run(
            ["uci", "-q", "get", f"{UCI_PACKAGE}.{UCI_SECTION}.{key}"],
            capture_output=True,
            text=True,
            timeout=2,
        )
        if result.returncode == 0:
            value = result.stdout.strip()
            if value:
                return value.split()
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass
    return None


def _load_from_toml(config_path: Optional[str]) -> dict:
    """Load configuration from TOML file."""
    if tomllib is None:
        return {}

    paths_to_try = [config_path] if config_path else DEFAULT_CONFIG_PATHS

    for path in paths_to_try:
        if path is None:
            continue
        expanded = Path(path).expanduser()
        if expanded.exists():
            try:
                with open(expanded, "rb") as f:
                    return tomllib.load(f)
            except Exception:
                continue

    return {}


def _load_from_uci(config: Config) -> None:
    """Overlay UCI values onto config object."""
    if not _is_openwrt():
        return

    # [modem] section
    val = _uci_get("device")
    if val:
        config.device = val

    val = _uci_get("baudrate")
    if val:
        try:
            config.baudrate = int(val)
        except ValueError:
            pass

    val = _uci_get("timeout")
    if val:
        try:
            config.timeout = float(val)
        except ValueError:
            pass

    # [monitor] section
    val = _uci_get("refresh_interval")
    if val:
        try:
            config.refresh_interval = float(val)
        except ValueError:
            pass

    val = _uci_get("beep_interval")
    if val:
        try:
            config.beep_interval = float(val)
        except ValueError:
            pass

    val = _uci_get("beeps_enabled")
    if val:
        config.beeps_enabled = val.lower() in ("1", "true", "yes", "on")

    # [bands] section
    bands = _uci_get_list("lte_bands")
    if bands:
        try:
            config.lte_bands = [int(b) for b in bands]
        except ValueError:
            pass

    bands = _uci_get_list("nr5g_bands")
    if bands:
        try:
            config.nr5g_bands = [int(b) for b in bands]
        except ValueError:
            pass


def load_config(config_path: Optional[str] = None) -> Config:
    """Load configuration from TOML file with UCI overlay on OpenWRT.

    Priority (highest to lowest):
    1. UCI config (OpenWRT only)
    2. TOML config file
    3. Built-in defaults

    Args:
        config_path: Explicit path to config file. If None, searches default paths.

    Returns:
        Config object with loaded settings.
    """
    config = Config()

    # Load from TOML first (base config)
    toml_data = _load_from_toml(config_path)

    # Apply TOML [modem] section
    modem = toml_data.get("modem", {})
    if "device" in modem:
        config.device = modem["device"]
    if "baudrate" in modem:
        config.baudrate = int(modem["baudrate"])
    if "timeout" in modem:
        config.timeout = float(modem["timeout"])

    # Apply TOML [monitor] section
    monitor = toml_data.get("monitor", {})
    if "refresh_interval" in monitor:
        config.refresh_interval = float(monitor["refresh_interval"])
    if "beep_interval" in monitor:
        config.beep_interval = float(monitor["beep_interval"])
    if "beeps_enabled" in monitor:
        config.beeps_enabled = bool(monitor["beeps_enabled"])

    # Apply TOML [bands] section
    bands = toml_data.get("bands", {})
    if "lte" in bands:
        config.lte_bands = list(bands["lte"])
    if "nr5g" in bands:
        config.nr5g_bands = list(bands["nr5g"])

    # Overlay UCI config (highest priority on OpenWRT)
    _load_from_uci(config)

    return config


def generate_uci_defaults() -> str:
    """Generate default UCI config for /etc/config/quectel.

    Returns:
        UCI config file content as string
    """
    return f"""config {UCI_SECTION} '{UCI_SECTION}'
\toption device '/dev/ttyUSB2'
\toption baudrate '115200'
\toption timeout '2.0'
\toption refresh_interval '5.0'
\toption beep_interval '0.6'
\toption beeps_enabled '1'
\tlist lte_bands '1'
\tlist lte_bands '3'
\tlist lte_bands '7'
\tlist lte_bands '20'
\tlist nr5g_bands '78'
"""
