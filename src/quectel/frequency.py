"""EARFCN and NR-ARFCN to frequency conversion."""

from typing import Optional, Tuple

# LTE EARFCN to frequency table
# Format: (band, earfcn_start, earfcn_end, freq_low_mhz, offset)
LTE_BANDS = [
    (1, 0, 599, 2110.0, 0),           # B1 (2100 MHz FDD)
    (3, 1200, 1949, 1805.0, 1200),    # B3 (1800 MHz FDD)
    (7, 2750, 3449, 2620.0, 2750),    # B7 (2600 MHz FDD)
    (20, 6150, 6449, 791.0, 6150),    # B20 (800 MHz FDD)
    (28, 9210, 9659, 758.0, 9210),    # B28 (700 MHz FDD)
    (32, 9920, 10359, 1452.0, 9920),  # B32 (1500 MHz SDL)
    (38, 37750, 38249, 2570.0, 37750),  # B38 (2600 MHz TDD)
    (40, 38650, 39649, 2300.0, 38650),  # B40 (2300 MHz TDD)
]

# NR5G NR-ARFCN ranges for common bands
# Format: (band, arfcn_start, arfcn_end, global_freq_offset_khz, channel_raster_khz)
# For FR1 (< 3 GHz): F = F_REF_Offs + delta_F_Global * (ARFCN - ARFCN_Offs)
# For N78: 3300-3800 MHz, ARFCN 620000-653333
NR5G_BANDS = [
    (78, 620000, 653333, 3000000, 15),  # N78 (3.3-3.8 GHz)
]


def earfcn_to_mhz(earfcn: int) -> Tuple[Optional[float], Optional[int]]:
    """Convert LTE EARFCN to frequency in MHz and band number.

    Returns:
        Tuple of (frequency_mhz, band_number), or (None, None) if not found.
    """
    for band, start, end, freq_low, offset in LTE_BANDS:
        if start <= earfcn <= end:
            freq = freq_low + 0.1 * (earfcn - offset)
            return (freq, band)
    return (None, None)


def nrarfcn_to_mhz(arfcn: int) -> Tuple[Optional[float], Optional[int]]:
    """Convert NR5G NR-ARFCN to frequency in MHz and band number.

    For FR1 bands (N78 in this case):
    F = 3000 MHz + 0.015 MHz * (ARFCN - 600000)

    Returns:
        Tuple of (frequency_mhz, band_number), or (None, None) if not found.
    """
    for band, start, end, _, _ in NR5G_BANDS:
        if start <= arfcn <= end:
            # FR1 formula for N78
            freq = 3000.0 + 0.015 * (arfcn - 600000)
            return (freq, band)
    return (None, None)


def format_frequency(earfcn_or_arfcn: int, is_5g: bool = False) -> str:
    """Format EARFCN/NR-ARFCN as human-readable frequency string.

    Returns:
        String like "1845.0 MHz (B3)" or "3732.5 MHz (N78)"
    """
    if is_5g:
        freq, band = nrarfcn_to_mhz(earfcn_or_arfcn)
        prefix = "N"
    else:
        freq, band = earfcn_to_mhz(earfcn_or_arfcn)
        prefix = "B"

    if freq is None:
        return f"Unknown ({earfcn_or_arfcn})"

    return f"{freq:.1f} MHz ({prefix}{band})"


# LTE Bandwidth mappings
# QENG uses an index (0-5), QCAINFO uses RB count
LTE_BW_INDEX_MAP = {
    0: "1.4 MHz",
    1: "3 MHz",
    2: "5 MHz",
    3: "10 MHz",
    4: "15 MHz",
    5: "20 MHz",
}

LTE_BW_RB_MAP = {
    6: "1.4 MHz",
    15: "3 MHz",
    25: "5 MHz",
    50: "10 MHz",
    75: "15 MHz",
    100: "20 MHz",
}

# NR5G Bandwidth index mapping (SCS 30 kHz)
NR5G_BW_INDEX_MAP = {
    0: "5 MHz",
    1: "10 MHz",
    2: "15 MHz",
    3: "20 MHz",
    4: "25 MHz",
    5: "30 MHz",
    6: "40 MHz",
    7: "50 MHz",
    8: "60 MHz",
    9: "70 MHz",
    10: "80 MHz",
    11: "90 MHz",
    12: "100 MHz",
}


def format_lte_bandwidth(index: int, from_qcainfo: bool = False) -> str:
    """Format LTE bandwidth from index or RB count."""
    if from_qcainfo:
        return LTE_BW_RB_MAP.get(index, f"? ({index} RB)")
    return LTE_BW_INDEX_MAP.get(index, f"? (idx {index})")


def format_nr5g_bandwidth(index: int) -> str:
    """Format NR5G bandwidth from index."""
    return NR5G_BW_INDEX_MAP.get(index, f"? (idx {index})")
