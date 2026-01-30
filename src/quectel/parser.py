"""Parsers for Quectel AT command responses."""

import re
from typing import Dict, List, Optional, Tuple

from .models import (
    CarrierComponent,
    DeviceInfo,
    LteServingCell,
    NetworkInfo,
    NeighbourCell,
    Nr5gServingCell,
)


def _clean_value(val: str) -> str:
    """Remove quotes and whitespace from a value."""
    return val.strip().strip('"')


def _parse_int(val: str) -> Optional[int]:
    """Parse integer, returning None for invalid/missing values."""
    val = _clean_value(val)
    if not val or val == "-":
        return None
    try:
        return int(val)
    except ValueError:
        return None


def _parse_float(val: str) -> Optional[float]:
    """Parse float, returning None for invalid/missing values."""
    val = _clean_value(val)
    if not val or val == "-":
        return None
    try:
        return float(val)
    except ValueError:
        return None


def _parse_hex(val: str) -> Optional[int]:
    """Parse hex string to int, returning None for invalid values."""
    val = _clean_value(val)
    if not val or val == "-":
        return None
    try:
        return int(val, 16)
    except ValueError:
        return None


def parse_ati(response: str) -> Optional[DeviceInfo]:
    """Parse ATI response.

    Example:
        Quectel
        RM520N-GL
        Revision: RM520NGLAAR03A03M4G

        OK
    """
    lines = [l.strip() for l in response.splitlines() if l.strip()]
    lines = [l for l in lines if l not in ("OK", "ERROR")]

    if len(lines) < 3:
        return None

    manufacturer = lines[0]
    model = lines[1]
    revision = ""

    for line in lines[2:]:
        if line.startswith("Revision:"):
            revision = line.replace("Revision:", "").strip()
            break

    return DeviceInfo(
        manufacturer=manufacturer,
        model=model,
        revision=revision,
    )


def parse_qspn(response: str) -> Optional[NetworkInfo]:
    """Parse AT+QSPN response.

    Example:
        +QSPN: "I TIM","TIM","",0,"22201"
    """
    match = re.search(r'\+QSPN:\s*"([^"]*)","([^"]*)",[^,]*,[^,]*,"(\d+)"', response)
    if not match:
        return None

    full_name = match.group(1)
    short_name = match.group(2)
    mcc_mnc = match.group(3)

    if len(mcc_mnc) >= 5:
        mcc = int(mcc_mnc[:3])
        mnc = int(mcc_mnc[3:])
    else:
        mcc = 0
        mnc = 0

    return NetworkInfo(
        full_name=full_name,
        short_name=short_name,
        mcc=mcc,
        mnc=mnc,
    )


def parse_qeng_servingcell(
    response: str,
) -> Tuple[Optional[LteServingCell], Optional[Nr5gServingCell]]:
    """Parse AT+QENG="servingcell" response.

    Example:
        +QENG: "servingcell","NOCONN"
        +QENG: "LTE","FDD",222,01,328261F,280,275,1,4,4,BE3,-99,-14,-66,7,4,30,-
        +QENG: "NR5G-NSA",222,01,920,-96,18,-10,648768,78,10,1
    """
    lte_cell = None
    nr5g_cell = None

    for line in response.splitlines():
        line = line.strip()
        if not line.startswith("+QENG:"):
            continue

        # Remove +QENG: prefix and split by comma
        content = line[7:].strip()
        parts = [_clean_value(p) for p in content.split(",")]

        if len(parts) < 2:
            continue

        # LTE serving cell
        # "LTE","FDD",222,01,328261F,280,275,1,4,4,BE3,-99,-14,-66,7,4,30,-
        if parts[0] == "LTE" and len(parts) >= 17:
            try:
                lte_cell = LteServingCell(
                    mode=parts[1],
                    mcc=int(parts[2]),
                    mnc=int(parts[3]),
                    cell_id=_parse_hex(parts[4]) or 0,
                    pci=int(parts[5]),
                    earfcn=int(parts[6]),
                    band=int(parts[7]),
                    ul_bandwidth_idx=_parse_int(parts[8]) or 0,
                    dl_bandwidth_idx=_parse_int(parts[9]) or 0,
                    tac=_parse_hex(parts[10]) or 0,
                    rsrp=_parse_int(parts[11]) or 0,
                    rsrq=_parse_int(parts[12]) or 0,
                    rssi=_parse_int(parts[13]) or 0,
                    sinr=_parse_float(parts[14]) or 0.0,
                    cqi=_parse_int(parts[15]),
                    tx_power=_parse_float(parts[16]) if parts[16] != "-" else None,
                )
                if lte_cell.tx_power is not None:
                    lte_cell = LteServingCell(
                        **{
                            **lte_cell.__dict__,
                            "tx_power": lte_cell.tx_power / 10.0,
                        }
                    )
            except (ValueError, IndexError):
                pass

        # NR5G-NSA serving cell
        # "NR5G-NSA",222,01,920,-96,18,-10,648768,78,10,1
        elif "NR5G-NSA" in parts[0] and len(parts) >= 10:
            try:
                nr5g_cell = Nr5gServingCell(
                    mcc=int(parts[1]),
                    mnc=int(parts[2]),
                    pci=int(parts[3]),
                    rsrp=int(parts[4]),
                    sinr=float(parts[5]),
                    rsrq=int(parts[6]),
                    arfcn=int(parts[7]),
                    band=int(parts[8]),
                    bandwidth_idx=int(parts[9]),
                )
            except (ValueError, IndexError):
                pass

    return (lte_cell, nr5g_cell)


def _pcell_state(code: str) -> str:
    """Convert PCell state code to string."""
    states = {
        "0": "Idle",
        "1": "Registered",
        "2": "Searching",
        "3": "Denied",
        "4": "Unknown",
        "5": "Roaming",
    }
    return states.get(code, "N/A")


def _scell_state(code: str) -> str:
    """Convert SCell state code to string."""
    states = {
        "0": "Deconfigured",
        "1": "Inactive",
        "2": "Active",
    }
    return states.get(code, "N/A")


def parse_qcainfo(response: str) -> List[CarrierComponent]:
    """Parse AT+QCAINFO response.

    Examples:
        +QCAINFO: "PCC",275,75,"LTE BAND 1",1,280,-99,-14,-67,-4
        +QCAINFO: "SCC",1350,100,"LTE BAND 3",1,240,-95,-18,-68,-10,0,-,-
        +QCAINFO: "SCC",648768,10,"NR5G BAND 78",920
    """
    components = []

    for line in response.splitlines():
        line = line.strip()
        if not line.startswith("+QCAINFO:"):
            continue

        content = line[10:].strip()
        parts = [_clean_value(p) for p in content.split(",")]

        if len(parts) < 5:
            continue

        c_type = parts[0]
        earfcn = _parse_int(parts[1]) or 0
        bw_raw = _parse_int(parts[2]) or 0
        band_name = parts[3]
        pci = 0
        state = None
        rsrp = None
        rsrq = None
        sinr = None
        ul_configured = None
        ul_band = None
        ul_earfcn = None

        try:
            if c_type == "PCC":
                # PCC,earfcn,bw,band,state,pci,rsrp,rsrq,rssi,sinr
                if len(parts) >= 10:
                    state = _pcell_state(parts[4])
                    pci = _parse_int(parts[5]) or 0
                    rsrp = _parse_int(parts[6])
                    rsrq = _parse_int(parts[7])
                    sinr = _parse_float(parts[9])
            else:  # SCC
                if len(parts) == 5:
                    # NR5G SCC: SCC,arfcn,bw_idx,band,pci
                    pci = _parse_int(parts[4]) or 0
                elif len(parts) == 9:
                    # SCC without signal info: SCC,earfcn,bw,band,state,pci,ul_cfg,ul_band,ul_earfcn
                    state = _scell_state(parts[4])
                    pci = _parse_int(parts[5]) or 0
                    ul_configured = _parse_int(parts[6])
                    ul_band = parts[7] if parts[7] != "-" else None
                    ul_earfcn = _parse_int(parts[8])
                elif len(parts) == 12:
                    # SCC with signal but different order
                    state = _scell_state(parts[4])
                    pci = _parse_int(parts[5]) or 0
                    ul_configured = _parse_int(parts[6])
                    ul_band = parts[7] if parts[7] != "-" else None
                    ul_earfcn = _parse_int(parts[8])
                    rsrp = _parse_int(parts[9])
                    rsrq = _parse_int(parts[10])
                    sinr = _parse_float(parts[11])
                elif len(parts) >= 13:
                    # Full SCC: SCC,earfcn,bw,band,state,pci,rsrp,rsrq,rssi,sinr,ul_cfg,ul_band,ul_earfcn
                    state = _scell_state(parts[4])
                    pci = _parse_int(parts[5]) or 0
                    rsrp = _parse_int(parts[6])
                    rsrq = _parse_int(parts[7])
                    sinr = _parse_float(parts[9])
                    ul_configured = _parse_int(parts[10])
                    ul_band = parts[11] if parts[11] != "-" else None
                    ul_earfcn = _parse_int(parts[12])

            components.append(
                CarrierComponent(
                    component_type=c_type,
                    earfcn=earfcn,
                    bandwidth_raw=bw_raw,
                    band_name=band_name,
                    state=state,
                    pci=pci,
                    rsrp=rsrp,
                    rsrq=rsrq,
                    sinr=sinr,
                    ul_configured=ul_configured,
                    ul_band=ul_band,
                    ul_earfcn=ul_earfcn,
                )
            )
        except (ValueError, IndexError):
            continue

    return components


def parse_qeng_neighbourcell(response: str) -> List[NeighbourCell]:
    """Parse AT+QENG="neighbourcell" response.

    Examples:
        +QENG: "neighbourcell intra","LTE",275,280,-14,-99,-67,-,-,-,-,-,-
        +QENG: "neighbourcell inter","LTE",1350,240,-18,-95,-68,-,-,-,-,-
    """
    cells = []

    for line in response.splitlines():
        line = line.strip()
        if "neighbourcell" not in line:
            continue

        # Determine cell type (intra/inter)
        if "intra" in line:
            cell_type = "intra"
        elif "inter" in line:
            cell_type = "inter"
        else:
            continue

        # Remove prefix and clean up
        content = line.replace('+QENG: "neighbourcell intra",', "")
        content = content.replace('+QENG: "neighbourcell inter",', "")
        content = content.replace('"', "")
        parts = [p.strip() for p in content.split(",")]

        if len(parts) < 6:
            continue

        try:
            tech = parts[0]
            if tech != "LTE":
                continue

            cells.append(
                NeighbourCell(
                    cell_type=cell_type,
                    technology=tech,
                    earfcn=int(parts[1]),
                    pci=int(parts[2]),
                    rsrq=_parse_int(parts[3]) or 0,
                    rsrp=_parse_int(parts[4]) or 0,
                    rssi=_parse_int(parts[5]) or 0,
                )
            )
        except (ValueError, IndexError):
            continue

    return cells


def parse_qnwprefcfg(response: str) -> Dict[str, str]:
    """Parse AT+QNWPREFCFG responses.

    Examples:
        +QNWPREFCFG: "mode_pref",AUTO
        +QNWPREFCFG: "nsa_nr5g_band",78
        +QNWPREFCFG: "lte_band",1:3:7:20
    """
    config = {}

    for line in response.splitlines():
        line = line.strip()
        if not line.startswith("+QNWPREFCFG:"):
            continue

        content = line[13:].strip()
        match = re.match(r'"([^"]+)",(.+)', content)
        if match:
            key = match.group(1)
            value = match.group(2).strip()
            config[key] = value

    return config
