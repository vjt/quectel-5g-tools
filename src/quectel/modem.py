"""Modem communication backends and high-level Modem interface."""

import glob
import subprocess
import time
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Tuple

from .config import Config
from .models import (
    CarrierComponent,
    DeviceInfo,
    LteServingCell,
    NetworkInfo,
    NeighbourCell,
    Nr5gServingCell,
)
from .parser import (
    parse_ati,
    parse_qcainfo,
    parse_qeng_neighbourcell,
    parse_qeng_servingcell,
    parse_qnwprefcfg,
    parse_qspn,
)


class ModemBackend(ABC):
    """Abstract base class for modem communication backends."""

    @abstractmethod
    def send_command(self, command: str, timeout: float = 2.0) -> str:
        """Send AT command and return response.

        Args:
            command: AT command to send (e.g., "ATI" or "AT+QSPN")
            timeout: Maximum time to wait for response

        Returns:
            Raw response string from modem
        """
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if this backend is available on the current system."""
        pass


class GlModemBackend(ModemBackend):
    """Backend using gl_modem CLI (GL.INET devices)."""

    def __init__(self, bus_id: str = "1-1.2"):
        self.bus_id = bus_id

    def send_command(self, command: str, timeout: float = 4.0) -> str:
        cmd = f"gl_modem -B {self.bus_id} AT '{command}'"
        try:
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            output = result.stdout
            if result.returncode != 0 and result.stderr:
                output += "\n" + result.stderr
            return output.replace("\r", "").strip()
        except subprocess.TimeoutExpired:
            return "ERROR: Timeout"
        except Exception as e:
            return f"ERROR: {e}"

    def is_available(self) -> bool:
        try:
            result = subprocess.run(
                ["which", "gl_modem"],
                capture_output=True,
                timeout=2,
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False


class SerialBackend(ModemBackend):
    """Backend using direct serial communication via pyserial."""

    def __init__(
        self,
        device: str,
        baudrate: int = 115200,
        timeout: float = 2.0,
    ):
        self.device = device
        self.baudrate = baudrate
        self.timeout = timeout
        self._serial = None

    def _ensure_connected(self):
        if self._serial is None:
            try:
                import serial

                self._serial = serial.Serial(
                    self.device,
                    baudrate=self.baudrate,
                    timeout=self.timeout,
                )
            except ImportError:
                raise RuntimeError("pyserial not installed")

    def send_command(self, command: str, timeout: float = 2.0) -> str:
        self._ensure_connected()

        # Clear any pending data
        self._serial.reset_input_buffer()

        # Send command with CR
        self._serial.write(f"{command}\r".encode())

        # Wait for response
        response_lines = []
        end_time = time.time() + timeout

        while time.time() < end_time:
            if self._serial.in_waiting:
                line = self._serial.readline().decode("utf-8", errors="ignore")
                line = line.strip()
                if line:
                    response_lines.append(line)
                    # Check for end of response
                    if line in ("OK", "ERROR"):
                        break
            else:
                time.sleep(0.01)

        return "\n".join(response_lines)

    def is_available(self) -> bool:
        try:
            import serial

            return True
        except ImportError:
            return False

    def close(self):
        if self._serial:
            self._serial.close()
            self._serial = None


def auto_detect_port() -> Optional[str]:
    """Auto-detect Quectel modem AT command port.

    Probes /dev/ttyUSB* devices looking for a Quectel modem.

    Returns:
        Device path (e.g., "/dev/ttyUSB2") or None if not found.
    """
    candidates = sorted(glob.glob("/dev/ttyUSB*"))

    for device in candidates:
        try:
            backend = SerialBackend(device, timeout=1.0)
            response = backend.send_command("ATI", timeout=2.0)
            backend.close()

            if "Quectel" in response:
                return device
        except Exception:
            continue

    return None


class Modem:
    """High-level interface for Quectel modem operations."""

    def __init__(self, backend: ModemBackend):
        self.backend = backend

    @classmethod
    def from_config(cls, config: Config) -> "Modem":
        """Create Modem instance from configuration."""
        if config.backend == "gl_modem":
            backend = GlModemBackend(bus_id=config.modem_bus or "1-1.2")
        else:
            device = config.modem_device
            if device is None:
                device = auto_detect_port()
            if device is None:
                raise RuntimeError("No modem device found")
            backend = SerialBackend(
                device=device,
                baudrate=config.serial_baudrate,
                timeout=config.serial_timeout,
            )
        return cls(backend)

    def send_raw(self, command: str, timeout: float = 4.0) -> str:
        """Send raw AT command and return response."""
        return self.backend.send_command(command, timeout)

    def get_device_info(self) -> Optional[DeviceInfo]:
        """Get device identification."""
        response = self.backend.send_command("ATI")
        return parse_ati(response)

    def get_network_info(self) -> Optional[NetworkInfo]:
        """Get network operator information."""
        response = self.backend.send_command("AT+QSPN")
        return parse_qspn(response)

    def get_serving_cell(
        self,
    ) -> Tuple[Optional[LteServingCell], Optional[Nr5gServingCell]]:
        """Get serving cell information."""
        response = self.backend.send_command('AT+QENG="servingcell"')
        return parse_qeng_servingcell(response)

    def get_carrier_aggregation(self) -> List[CarrierComponent]:
        """Get carrier aggregation information."""
        response = self.backend.send_command("AT+QCAINFO")
        return parse_qcainfo(response)

    def get_neighbour_cells(self) -> List[NeighbourCell]:
        """Get neighbour cell information."""
        response = self.backend.send_command('AT+QENG="neighbourcell"')
        return parse_qeng_neighbourcell(response)

    def get_band_config(self) -> Dict[str, str]:
        """Get current band configuration."""
        config = {}

        response = self.backend.send_command('AT+QNWPREFCFG="mode_pref"')
        config.update(parse_qnwprefcfg(response))

        response = self.backend.send_command('AT+QNWPREFCFG="lte_band"')
        config.update(parse_qnwprefcfg(response))

        response = self.backend.send_command('AT+QNWPREFCFG="nsa_nr5g_band"')
        config.update(parse_qnwprefcfg(response))

        return config

    def set_lte_bands(self, bands: List[int]) -> bool:
        """Set allowed LTE bands.

        Args:
            bands: List of band numbers (e.g., [1, 3, 7, 20])

        Returns:
            True if successful
        """
        band_str = ":".join(str(b) for b in bands)
        response = self.backend.send_command(
            f'AT+QNWPREFCFG="lte_band",{band_str}'
        )
        return "OK" in response

    def set_nr5g_bands(self, bands: List[int]) -> bool:
        """Set allowed NR5G bands.

        Args:
            bands: List of band numbers (e.g., [78])

        Returns:
            True if successful
        """
        band_str = ":".join(str(b) for b in bands)
        response = self.backend.send_command(
            f'AT+QNWPREFCFG="nsa_nr5g_band",{band_str}'
        )
        return "OK" in response
