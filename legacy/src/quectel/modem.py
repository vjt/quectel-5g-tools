"""Modem communication via serial port."""

import time
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


class ModemError(Exception):
    """Error communicating with modem."""
    pass


class Modem:
    """Interface for Quectel modem AT commands via serial port."""

    def __init__(self, device: str, baudrate: int = 115200, timeout: float = 2.0):
        """Initialize modem connection.

        Args:
            device: Serial device path (e.g., /dev/ttyUSB2)
            baudrate: Serial baudrate (default 115200)
            timeout: Read timeout in seconds
        """
        self.device = device
        self.baudrate = baudrate
        self.timeout = timeout
        self._serial = None

    def _ensure_connected(self):
        """Ensure serial connection is open."""
        if self._serial is not None:
            return

        try:
            import serial
        except ImportError:
            raise ModemError("pyserial not installed. Run: pip install pyserial")

        try:
            self._serial = serial.Serial(
                self.device,
                baudrate=self.baudrate,
                timeout=self.timeout,
            )
        except serial.SerialException as e:
            raise ModemError(f"Cannot open {self.device}: {e}")

    def close(self):
        """Close serial connection."""
        if self._serial:
            self._serial.close()
            self._serial = None

    def send_raw(self, command: str, timeout: Optional[float] = None) -> str:
        """Send raw AT command and return response.

        Args:
            command: AT command to send
            timeout: Override timeout for this command

        Returns:
            Raw response string
        """
        self._ensure_connected()

        # Clear any pending data
        self._serial.reset_input_buffer()

        # Send command with CR
        self._serial.write(f"{command}\r".encode())

        # Wait for response
        response_lines = []
        read_timeout = timeout or self.timeout
        end_time = time.time() + read_timeout

        while time.time() < end_time:
            if self._serial.in_waiting:
                line = self._serial.readline().decode("utf-8", errors="ignore")
                line = line.strip()
                if line:
                    response_lines.append(line)
                    if line in ("OK", "ERROR"):
                        break
            else:
                time.sleep(0.01)

        return "\n".join(response_lines)

    @classmethod
    def from_config(cls, config: Config) -> "Modem":
        """Create Modem instance from configuration."""
        return cls(
            device=config.device,
            baudrate=config.baudrate,
            timeout=config.timeout,
        )

    def get_device_info(self) -> Optional[DeviceInfo]:
        """Get device identification."""
        response = self.send_raw("ATI")
        return parse_ati(response)

    def get_network_info(self) -> Optional[NetworkInfo]:
        """Get network operator information."""
        response = self.send_raw("AT+QSPN")
        return parse_qspn(response)

    def get_serving_cell(
        self,
    ) -> Tuple[Optional[LteServingCell], Optional[Nr5gServingCell]]:
        """Get serving cell information."""
        response = self.send_raw('AT+QENG="servingcell"')
        return parse_qeng_servingcell(response)

    def get_carrier_aggregation(self) -> List[CarrierComponent]:
        """Get carrier aggregation information."""
        response = self.send_raw("AT+QCAINFO")
        return parse_qcainfo(response)

    def get_neighbour_cells(self) -> List[NeighbourCell]:
        """Get neighbour cell information."""
        response = self.send_raw('AT+QENG="neighbourcell"')
        return parse_qeng_neighbourcell(response)

    def get_band_config(self) -> Dict[str, str]:
        """Get current band configuration."""
        config = {}

        response = self.send_raw('AT+QNWPREFCFG="mode_pref"')
        config.update(parse_qnwprefcfg(response))

        response = self.send_raw('AT+QNWPREFCFG="lte_band"')
        config.update(parse_qnwprefcfg(response))

        response = self.send_raw('AT+QNWPREFCFG="nsa_nr5g_band"')
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
        response = self.send_raw(f'AT+QNWPREFCFG="lte_band",{band_str}')
        return "OK" in response

    def set_nr5g_bands(self, bands: List[int]) -> bool:
        """Set allowed NR5G bands.

        Args:
            bands: List of band numbers (e.g., [78])

        Returns:
            True if successful
        """
        band_str = ":".join(str(b) for b in bands)
        response = self.send_raw(f'AT+QNWPREFCFG="nsa_nr5g_band",{band_str}')
        return "OK" in response
