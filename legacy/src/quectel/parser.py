"""Parsers for Quectel AT command responses."""

from typing import Dict, Iterator, List, Optional, Tuple

from .models import (
    CarrierComponent,
    DeviceInfo,
    LteServingCell,
    NetworkInfo,
    NeighbourCell,
    Nr5gServingCell,
)


def parse_response(text: str, prefix: str) -> Iterator[List[str]]:
    """Parse AT command response lines with a common pattern.

    AT command responses follow a consistent format:
    - Empty lines to skip
    - Lines starting with prefix followed by colon, then comma-separated values
    - Values may be quoted

    Args:
        text: Raw response text from modem
        prefix: Command prefix to match (e.g., "+QSPN", "+QENG")

    Yields:
        List of stripped, unquoted values for each matching line
    """
    for line in text.splitlines():
        line = line.strip()
        if not line or line in ("OK", "ERROR"):
            continue

        if not line.startswith(prefix + ":"):
            continue

        # Remove prefix and colon
        content = line[len(prefix) + 1:].strip()

        # Split on comma and strip quotes/whitespace from each value
        values = []
        for val in content.split(","):
            val = val.strip()
            if val.startswith('"') and val.endswith('"'):
                val = val[1:-1]
            values.append(val)

        yield values


def parse_int(val: str) -> Optional[int]:
    """Parse integer, returning None for invalid/missing values."""
    if not val or val == "-":
        return None
    try:
        return int(val)
    except ValueError:
        return None


def parse_float(val: str) -> Optional[float]:
    """Parse float, returning None for invalid/missing values."""
    if not val or val == "-":
        return None
    try:
        return float(val)
    except ValueError:
        return None


def parse_hex(val: str) -> Optional[int]:
    """Parse hex string to int, returning None for invalid values."""
    if not val or val == "-":
        return None
    try:
        return int(val, 16)
    except ValueError:
        return None


def parse_ati(response: str) -> Optional[DeviceInfo]:
    """Parse ATI response.

    ATI is special - it doesn't follow the +PREFIX: format.
    It returns plain lines: manufacturer, model, revision.
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

    Example: +QSPN: "I TIM","TIM","",0,"22201"
    """
    for values in parse_response(response, "+QSPN"):
        if len(values) < 5:
            continue

        full_name = values[0]
        short_name = values[1]
        mcc_mnc = values[4]

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

    return None


def parse_qeng_servingcell(
    response: str,
) -> Tuple[Optional[LteServingCell], Optional[Nr5gServingCell]]:
    """Parse AT+QENG="servingcell" response.

    Example lines:
        +QENG: "servingcell","NOCONN"
        +QENG: "LTE","FDD",222,01,328261F,280,275,1,4,4,BE3,-99,-14,-66,7,4,30,-
        +QENG: "NR5G-NSA",222,01,920,-96,18,-10,648768,78,10,1
    """
    lte_cell = None
    nr5g_cell = None

    for values in parse_response(response, "+QENG"):
        if len(values) < 2:
            continue

        # LTE serving cell
        if values[0] == "LTE" and len(values) >= 17:
            try:
                tx_power_raw = parse_float(values[16])
                tx_power = tx_power_raw / 10.0 if tx_power_raw is not None else None

                lte_cell = LteServingCell(
                    mode=values[1],
                    mcc=int(values[2]),
                    mnc=int(values[3]),
                    cell_id=parse_hex(values[4]) or 0,
                    pci=int(values[5]),
                    earfcn=int(values[6]),
                    band=int(values[7]),
                    ul_bandwidth_idx=parse_int(values[8]) or 0,
                    dl_bandwidth_idx=parse_int(values[9]) or 0,
                    tac=parse_hex(values[10]) or 0,
                    rsrp=parse_int(values[11]) or 0,
                    rsrq=parse_int(values[12]) or 0,
                    rssi=parse_int(values[13]) or 0,
                    sinr=parse_float(values[14]) or 0.0,
                    cqi=parse_int(values[15]),
                    tx_power=tx_power,
                )
            except (ValueError, IndexError):
                pass

        # NR5G-NSA serving cell
        elif "NR5G-NSA" in values[0] and len(values) >= 10:
            try:
                nr5g_cell = Nr5gServingCell(
                    mcc=int(values[1]),
                    mnc=int(values[2]),
                    pci=int(values[3]),
                    rsrp=int(values[4]),
                    sinr=float(values[5]),
                    rsrq=int(values[6]),
                    arfcn=int(values[7]),
                    band=int(values[8]),
                    bandwidth_idx=int(values[9]),
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

    for values in parse_response(response, "+QCAINFO"):
        if len(values) < 5:
            continue

        c_type = values[0]
        earfcn = parse_int(values[1]) or 0
        bw_raw = parse_int(values[2]) or 0
        band_name = values[3]
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
                if len(values) >= 10:
                    state = _pcell_state(values[4])
                    pci = parse_int(values[5]) or 0
                    rsrp = parse_int(values[6])
                    rsrq = parse_int(values[7])
                    sinr = parse_float(values[9])
            else:  # SCC
                if len(values) == 5:
                    # NR5G SCC: SCC,arfcn,bw_idx,band,pci
                    pci = parse_int(values[4]) or 0
                elif len(values) == 9:
                    # SCC without signal: SCC,earfcn,bw,band,state,pci,ul_cfg,ul_band,ul_earfcn
                    state = _scell_state(values[4])
                    pci = parse_int(values[5]) or 0
                    ul_configured = parse_int(values[6])
                    ul_band = values[7] if values[7] != "-" else None
                    ul_earfcn = parse_int(values[8])
                elif len(values) == 12:
                    # SCC with signal but different order
                    state = _scell_state(values[4])
                    pci = parse_int(values[5]) or 0
                    ul_configured = parse_int(values[6])
                    ul_band = values[7] if values[7] != "-" else None
                    ul_earfcn = parse_int(values[8])
                    rsrp = parse_int(values[9])
                    rsrq = parse_int(values[10])
                    sinr = parse_float(values[11])
                elif len(values) >= 13:
                    # Full SCC
                    state = _scell_state(values[4])
                    pci = parse_int(values[5]) or 0
                    rsrp = parse_int(values[6])
                    rsrq = parse_int(values[7])
                    sinr = parse_float(values[9])
                    ul_configured = parse_int(values[10])
                    ul_band = values[11] if values[11] != "-" else None
                    ul_earfcn = parse_int(values[12])

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

    for values in parse_response(response, "+QENG"):
        if len(values) < 6:
            continue

        # First value is "neighbourcell intra" or "neighbourcell inter"
        cell_type_str = values[0]
        if "neighbourcell" not in cell_type_str:
            continue

        if "intra" in cell_type_str:
            cell_type = "intra"
        elif "inter" in cell_type_str:
            cell_type = "inter"
        else:
            continue

        try:
            tech = values[1]
            if tech != "LTE":
                continue

            cells.append(
                NeighbourCell(
                    cell_type=cell_type,
                    technology=tech,
                    earfcn=int(values[2]),
                    pci=int(values[3]),
                    rsrq=parse_int(values[4]) or 0,
                    rsrp=parse_int(values[5]) or 0,
                    rssi=parse_int(values[6]) or 0 if len(values) > 6 else 0,
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

    for values in parse_response(response, "+QNWPREFCFG"):
        if len(values) >= 2:
            key = values[0]
            value = values[1]
            config[key] = value

    return config
