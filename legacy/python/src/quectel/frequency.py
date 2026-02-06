"""EARFCN and NR-ARFCN to frequency conversion.

Complete 3GPP band tables for LTE and NR5G.
"""

from typing import Optional, Tuple

# =============================================================================
# LTE EARFCN to frequency conversion
# Based on 3GPP TS 36.101 Table 5.7.3-1
# Format: (band, earfcn_dl_low, earfcn_dl_high, f_dl_low_mhz, earfcn_offset)
# Formula: F_DL = F_DL_low + 0.1 * (EARFCN - EARFCN_offset)
# =============================================================================
LTE_BANDS = [
    # FDD Bands
    (1, 0, 599, 2110.0, 0),           # 2100 MHz IMT
    (2, 600, 1199, 1930.0, 600),      # 1900 MHz PCS
    (3, 1200, 1949, 1805.0, 1200),    # 1800 MHz DCS
    (4, 1950, 2399, 2110.0, 1950),    # AWS-1
    (5, 2400, 2649, 869.0, 2400),     # 850 MHz Cellular
    (6, 2650, 2749, 875.0, 2650),     # UMTS 800 (Japan)
    (7, 2750, 3449, 2620.0, 2750),    # 2600 MHz IMT-E
    (8, 3450, 3799, 925.0, 3450),     # 900 MHz E-GSM
    (9, 3800, 4149, 1844.9, 3800),    # 1800 MHz (Japan)
    (10, 4150, 4749, 2110.0, 4150),   # AWS-1+
    (11, 4750, 4949, 1475.9, 4750),   # 1500 MHz Lower (Japan)
    (12, 5010, 5179, 729.0, 5010),    # 700 MHz Lower A/B/C
    (13, 5180, 5279, 746.0, 5180),    # 700 MHz Upper C
    (14, 5280, 5379, 758.0, 5280),    # 700 MHz PS
    (17, 5730, 5849, 734.0, 5730),    # 700 MHz Lower B/C
    (18, 5850, 5999, 860.0, 5850),    # 800 MHz Lower (Japan)
    (19, 6000, 6149, 875.0, 6000),    # 800 MHz Upper (Japan)
    (20, 6150, 6449, 791.0, 6150),    # 800 MHz DD
    (21, 6450, 6599, 1495.9, 6450),   # 1500 MHz Upper (Japan)
    (22, 6600, 7399, 3510.0, 6600),   # 3500 MHz
    (23, 7500, 7699, 2180.0, 7500),   # AWS-4
    (24, 7700, 8039, 1525.0, 7700),   # L-Band
    (25, 8040, 8689, 1930.0, 8040),   # Extended PCS
    (26, 8690, 9039, 859.0, 8690),    # Extended 850
    (27, 9040, 9209, 852.0, 9040),    # 800 MHz SMR
    (28, 9210, 9659, 758.0, 9210),    # 700 MHz APT
    (29, 9660, 9769, 717.0, 9660),    # 700 MHz SDL
    (30, 9770, 9869, 2350.0, 9770),   # 2300 MHz WCS
    (31, 9870, 9919, 462.5, 9870),    # 450 MHz
    (32, 9920, 10359, 1452.0, 9920),  # 1500 MHz SDL
    (33, 36000, 36199, 1900.0, 36000),  # TDD 1900
    (34, 36200, 36349, 2010.0, 36200),  # TDD 2000
    (35, 36350, 36949, 1850.0, 36350),  # TDD PCS Lower
    (36, 36950, 37549, 1930.0, 36950),  # TDD PCS Upper
    (37, 37550, 37749, 1910.0, 37550),  # TDD PCS Center
    (38, 37750, 38249, 2570.0, 37750),  # TDD 2600
    (39, 38250, 38649, 1880.0, 38250),  # TDD 1900+
    (40, 38650, 39649, 2300.0, 38650),  # TDD 2300
    (41, 39650, 41589, 2496.0, 39650),  # TDD 2500
    (42, 41590, 43589, 3400.0, 41590),  # TDD 3500
    (43, 43590, 45589, 3600.0, 43590),  # TDD 3700
    (44, 45590, 46589, 703.0, 45590),   # TDD 700 APT
    (45, 46590, 46789, 1447.0, 46590),  # TDD 1500 L-Band
    (46, 46790, 54539, 5150.0, 46790),  # TDD Unlicensed
    (47, 54540, 55239, 5855.0, 54540),  # TDD V2X
    (48, 55240, 56739, 3550.0, 55240),  # TDD CBRS
    (49, 56740, 58239, 3550.0, 56740),  # TDD CBRS
    (50, 58240, 59089, 1432.0, 58240),  # TDD 1500 L-Band
    (51, 59090, 59139, 1427.0, 59090),  # TDD 1500 L-Band
    (52, 59140, 60139, 3300.0, 59140),  # TDD 3300
    (53, 60140, 60254, 2483.5, 60140),  # TDD 2400 S-Band
    (65, 65536, 66435, 2110.0, 65536),  # Extended IMT 2100
    (66, 66436, 67335, 2110.0, 66436),  # Extended AWS
    (67, 67336, 67535, 738.0, 67336),   # 700 EU SDL
    (68, 67536, 67835, 753.0, 67536),   # 700 ME
    (69, 67836, 68335, 2570.0, 67836),  # 2600 SDL
    (70, 68336, 68585, 1995.0, 68336),  # AWS-3
    (71, 68586, 68935, 617.0, 68586),   # 600 MHz
    (72, 68936, 68985, 461.0, 68936),   # 450 MHz PMR
    (73, 68986, 69035, 460.0, 68986),   # 450 MHz PMR
    (74, 69036, 69465, 1475.0, 69036),  # L-Band
    (75, 69466, 70315, 1432.0, 69466),  # L-Band SDL
    (76, 70316, 70365, 1427.0, 70316),  # L-Band SDL
    (85, 70366, 70545, 728.0, 70366),   # 700 Extended
    (87, 70546, 70595, 420.0, 70546),   # 410 MHz
    (88, 70596, 70645, 422.0, 70596),   # 410 MHz
]

# =============================================================================
# NR5G NR-ARFCN to frequency conversion
# Based on 3GPP TS 38.101-1 and TS 38.101-2
# FR1: Sub-6 GHz, FR2: mmWave
#
# For FR1 (< 3 GHz): F = F_REF_Offs + ΔF_Global × (ARFCN - ARFCN_Offs)
# Global frequency raster:
#   0-599999:     ΔF = 5 kHz,  F_REF = 0
#   600000-2016666: ΔF = 15 kHz, F_REF = 3000 MHz, ARFCN_off = 600000
#   2016667-3279165: ΔF = 60 kHz, F_REF = 24250.08 MHz, ARFCN_off = 2016667
#
# Format: (band, arfcn_low, arfcn_high, is_fr2)
# =============================================================================
# NR5G bands sorted by (arfcn_low, arfcn_high) to handle overlapping ranges correctly.
# When bands overlap, more specific (narrower) ranges are checked first.
NR5G_BANDS = [
    # FR1 Bands (Sub-6 GHz) - sorted by ARFCN range
    (71, 123400, 130400, False),    # n71: 600 MHz
    (12, 139800, 143200, False),    # n12: 700 MHz
    (83, 140600, 149600, False),    # n83: 700 MHz SUL
    (29, 141600, 143600, False),    # n29: 700 MHz SDL
    (85, 145600, 147600, False),    # n85: 700 MHz Extended SUL
    (28, 145800, 154600, False),    # n28: 700 MHz APT
    (67, 147600, 151600, False),    # n67: 700 MHz SDL
    (13, 149200, 151200, False),    # n13: 700 MHz
    (14, 151600, 153600, False),    # n14: 700 MHz PS
    (20, 151600, 160600, False),    # n20: 800 MHz DD
    (26, 162800, 169800, False),    # n26: 850 MHz Extended
    (18, 163000, 166000, False),    # n18: 800 MHz Japan
    (5, 164800, 169800, False),     # n5: 850 MHz
    (89, 164800, 169800, False),    # n89: 850 MHz SUL
    (82, 166400, 172400, False),    # n82: 800 MHz SUL
    (91, 166400, 172400, False),    # n91: 800/1500 MHz FDD
    (92, 166400, 172400, False),    # n92: 800/1500 MHz FDD
    (8, 176000, 183000, False),     # n8: 900 MHz
    (81, 176000, 183000, False),    # n81: 900 MHz SUL
    (100, 183880, 185000, False),   # n100: 900 MHz
    (51, 285400, 286400, False),    # n51: 1500 MHz
    (76, 285400, 286400, False),    # n76: L-Band SDL
    (93, 285400, 286400, False),    # n93: 1500 MHz SUL
    (50, 286400, 303400, False),    # n50: 1500 MHz
    (75, 286400, 303400, False),    # n75: L-Band SDL
    (94, 286400, 303400, False),    # n94: 1500 MHz SUL
    (74, 295000, 303600, False),    # n74: L-Band
    (99, 325300, 332100, False),    # n99: 1600 MHz SUL
    (86, 342000, 356000, False),    # n86: 1800 MHz SUL
    (3, 342000, 357000, False),     # n3: 1800 MHz DCS
    (80, 342000, 357000, False),    # n80: 1800 MHz SUL
    (2, 370000, 382000, False),     # n2: 1900 MHz PCS
    (25, 370000, 383000, False),    # n25: 1900 MHz Extended
    (39, 376000, 384000, False),    # n39: 1900 MHz TDD
    (98, 376000, 384000, False),    # n98: 1900 MHz SUL
    (101, 380000, 382000, False),   # n101: 1900 MHz
    (1, 384000, 396000, False),     # n1: 2100 MHz FDD
    (84, 384000, 396000, False),    # n84: 2100 MHz SUL
    (65, 384000, 399000, False),    # n65: 2100 MHz Extended
    (70, 399000, 404000, False),    # n70: AWS-3
    (34, 402000, 405000, False),    # n34: 2000 MHz TDD
    (95, 402000, 405000, False),    # n95: 2000 MHz TDD
    (66, 422000, 440000, False),    # n66: AWS Extended
    (40, 460000, 480000, False),    # n40: 2300 MHz TDD
    (30, 461000, 463000, False),    # n30: 2300 MHz
    (53, 496700, 499000, False),    # n53: 2.4 GHz
    (41, 499200, 537999, False),    # n41: 2500 MHz TDD (before n38, broader range)
    (90, 499200, 538000, False),    # n90: 2500 MHz TDD
    (7, 500000, 514000, False),     # n7: 2600 MHz
    (38, 514000, 524000, False),    # n38: 2600 MHz TDD (after n41, narrower range)
    (78, 620000, 653333, False),    # n78: 3.3-3.8 GHz TDD (before n77, narrower range)
    (77, 620000, 680000, False),    # n77: 3.3-4.2 GHz TDD (after n78, broader range)
    (97, 620000, 680000, False),    # n97: 2300 MHz SUL
    (48, 636667, 646666, False),    # n48: 3.5 GHz CBRS
    (79, 693334, 733333, False),    # n79: 4.4-5.0 GHz TDD
    (46, 743334, 795000, False),    # n46: 5 GHz Unlicensed
    (47, 790334, 795000, False),    # n47: 5.9 GHz V2X
    (102, 795000, 828333, False),   # n102: 6 GHz Unlicensed
    (96, 795000, 875000, False),    # n96: 6 GHz Unlicensed
    (104, 828334, 875000, False),   # n104: 6 GHz Unlicensed

    # FR2 Bands (mmWave)
    (258, 2016667, 2070832, True),  # n258: 26 GHz
    (257, 2054166, 2104165, True),  # n257: 28 GHz
    (261, 2070833, 2084999, True),  # n261: 28 GHz
    (260, 2229166, 2279165, True),  # n260: 39 GHz
    (259, 2270833, 2337499, True),  # n259: 41 GHz
    (262, 2399166, 2415832, True),  # n262: 47 GHz
    (263, 2564083, 2794249, True),  # n263: 60 GHz
]


def _nrarfcn_to_freq_khz(arfcn: int) -> int:
    """Convert NR-ARFCN to frequency in kHz using 3GPP formula."""
    if arfcn < 600000:
        # Range 0-599999: ΔF = 5 kHz
        return arfcn * 5
    elif arfcn < 2016667:
        # Range 600000-2016666: ΔF = 15 kHz, F_REF = 3000 MHz
        return 3000000 + (arfcn - 600000) * 15
    else:
        # Range 2016667-3279165: ΔF = 60 kHz, F_REF = 24250.08 MHz
        return 24250080 + (arfcn - 2016667) * 60


def earfcn_to_mhz(earfcn: int) -> Tuple[Optional[float], Optional[int]]:
    """Convert LTE EARFCN to frequency in MHz and band number.

    Args:
        earfcn: E-UTRA Absolute Radio Frequency Channel Number

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

    Args:
        arfcn: NR Absolute Radio Frequency Channel Number

    Returns:
        Tuple of (frequency_mhz, band_number), or (None, None) if not found.
    """
    for band, start, end, is_fr2 in NR5G_BANDS:
        if start <= arfcn <= end:
            freq_khz = _nrarfcn_to_freq_khz(arfcn)
            return (freq_khz / 1000.0, band)
    return (None, None)


def format_frequency(earfcn_or_arfcn: int, is_5g: bool = False) -> str:
    """Format EARFCN/NR-ARFCN as human-readable frequency string.

    Args:
        earfcn_or_arfcn: Channel number
        is_5g: True for NR-ARFCN, False for EARFCN

    Returns:
        String like "1845.0 MHz (B3)" or "3732.5 MHz (n78)"
    """
    if is_5g:
        freq, band = nrarfcn_to_mhz(earfcn_or_arfcn)
        prefix = "n"
    else:
        freq, band = earfcn_to_mhz(earfcn_or_arfcn)
        prefix = "B"

    if freq is None:
        return f"Unknown ({earfcn_or_arfcn})"

    return f"{freq:.1f} MHz ({prefix}{band})"


# =============================================================================
# Bandwidth mappings
# =============================================================================

# LTE Bandwidth: QENG uses index (0-5), QCAINFO uses RB count
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

# NR5G Bandwidth index mapping (SCS 15/30/60 kHz for FR1)
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
    13: "200 MHz",
    14: "400 MHz",
}


def format_lte_bandwidth(index: int, from_qcainfo: bool = False) -> str:
    """Format LTE bandwidth from index or RB count.

    Args:
        index: Bandwidth index (QENG) or RB count (QCAINFO)
        from_qcainfo: True if value is RB count from QCAINFO

    Returns:
        Formatted bandwidth string like "20 MHz"
    """
    if from_qcainfo:
        return LTE_BW_RB_MAP.get(index, f"? ({index} RB)")
    return LTE_BW_INDEX_MAP.get(index, f"? (idx {index})")


def format_nr5g_bandwidth(index: int) -> str:
    """Format NR5G bandwidth from index.

    Args:
        index: Bandwidth index from modem

    Returns:
        Formatted bandwidth string like "100 MHz"
    """
    return NR5G_BW_INDEX_MAP.get(index, f"? (idx {index})")
