"""Data classes for parsed modem responses."""

from dataclasses import dataclass
from typing import Optional


@dataclass
class DeviceInfo:
    """Device identification from ATI command."""
    manufacturer: str
    model: str
    revision: str


@dataclass
class NetworkInfo:
    """Network information from AT+QSPN command."""
    full_name: str
    short_name: str
    mcc: int
    mnc: int

    @property
    def mcc_mnc(self) -> str:
        return f"{self.mcc}-{self.mnc:02d}"


@dataclass
class LteServingCell:
    """LTE serving cell information from AT+QENG="servingcell"."""
    mode: str           # FDD/TDD
    mcc: int
    mnc: int
    cell_id: int        # hex cell ID as decimal
    pci: int
    earfcn: int
    band: int
    dl_bandwidth_idx: int
    ul_bandwidth_idx: int
    tac: int            # hex TAC as decimal
    rsrp: int
    rsrq: int
    rssi: int
    sinr: float
    cqi: Optional[int]
    tx_power: Optional[float]  # dBm (raw value / 10)

    @property
    def enodeb_id(self) -> int:
        """Extract eNodeB ID from cell ID (upper 20 bits)."""
        return self.cell_id >> 8

    @property
    def sector_id(self) -> int:
        """Extract sector ID from cell ID (lower 8 bits)."""
        return self.cell_id & 0xFF


@dataclass
class Nr5gServingCell:
    """5G NR serving cell information from AT+QENG="servingcell" (NSA mode)."""
    mcc: int
    mnc: int
    pci: int
    rsrp: int
    sinr: float
    rsrq: int
    arfcn: int
    band: int
    bandwidth_idx: int


@dataclass
class CarrierComponent:
    """Carrier aggregation component from AT+QCAINFO."""
    component_type: str     # PCC/SCC
    earfcn: int
    bandwidth_raw: int      # RB count for LTE, index for NR5G
    band_name: str          # "LTE BAND 3" or "NR5G BAND 78"
    state: Optional[str]    # "Active", "Inactive", etc.
    pci: int
    rsrp: Optional[int]
    rsrq: Optional[int]
    sinr: Optional[float]
    ul_configured: Optional[int]
    ul_band: Optional[str]
    ul_earfcn: Optional[int]

    @property
    def is_5g(self) -> bool:
        return "NR5G" in self.band_name

    @property
    def band_number(self) -> int:
        """Extract band number from band_name."""
        parts = self.band_name.split()
        if len(parts) >= 3:
            try:
                return int(parts[-1])
            except ValueError:
                pass
        return 0


@dataclass
class NeighbourCell:
    """Neighbour cell from AT+QENG="neighbourcell"."""
    cell_type: str      # "intra" or "inter"
    technology: str     # "LTE"
    earfcn: int
    pci: int
    rsrq: int
    rsrp: int
    rssi: int
