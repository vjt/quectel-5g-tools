"""Signal quality thresholds based on Quectel documentation."""

from enum import Enum
from typing import Optional


class SignalQuality(Enum):
    """Signal quality levels."""
    EXCELLENT = "excellent"
    GOOD = "good"
    FAIR = "fair"
    POOR = "poor"
    UNKNOWN = "unknown"


# RSRP thresholds (dBm) - applies to both LTE and NR5G
RSRP_THRESHOLDS = {
    SignalQuality.EXCELLENT: -80,
    SignalQuality.GOOD: -90,
    SignalQuality.FAIR: -100,
    SignalQuality.POOR: -110,
}

# RSRQ thresholds (dB) - applies to both LTE and NR5G
RSRQ_THRESHOLDS = {
    SignalQuality.EXCELLENT: -10,
    SignalQuality.GOOD: -12,
    SignalQuality.FAIR: -15,
    SignalQuality.POOR: -20,
}

# LTE SINR thresholds (dB)
LTE_SINR_THRESHOLDS = {
    SignalQuality.EXCELLENT: 20,
    SignalQuality.GOOD: 13,
    SignalQuality.FAIR: 0,
    SignalQuality.POOR: -20,
}

# NR5G SINR thresholds (dB)
NR5G_SINR_THRESHOLDS = {
    SignalQuality.EXCELLENT: 20,
    SignalQuality.GOOD: 13,
    SignalQuality.FAIR: 0,
    SignalQuality.POOR: -20,
}


def classify_rsrp(value: Optional[int]) -> SignalQuality:
    """Classify RSRP signal quality."""
    if value is None:
        return SignalQuality.UNKNOWN
    if value >= RSRP_THRESHOLDS[SignalQuality.EXCELLENT]:
        return SignalQuality.EXCELLENT
    if value >= RSRP_THRESHOLDS[SignalQuality.GOOD]:
        return SignalQuality.GOOD
    if value >= RSRP_THRESHOLDS[SignalQuality.FAIR]:
        return SignalQuality.FAIR
    return SignalQuality.POOR


def classify_rsrq(value: Optional[int]) -> SignalQuality:
    """Classify RSRQ signal quality."""
    if value is None:
        return SignalQuality.UNKNOWN
    if value >= RSRQ_THRESHOLDS[SignalQuality.EXCELLENT]:
        return SignalQuality.EXCELLENT
    if value >= RSRQ_THRESHOLDS[SignalQuality.GOOD]:
        return SignalQuality.GOOD
    if value >= RSRQ_THRESHOLDS[SignalQuality.FAIR]:
        return SignalQuality.FAIR
    return SignalQuality.POOR


def classify_sinr(value: Optional[float], is_5g: bool = False) -> SignalQuality:
    """Classify SINR signal quality."""
    if value is None:
        return SignalQuality.UNKNOWN
    thresholds = NR5G_SINR_THRESHOLDS if is_5g else LTE_SINR_THRESHOLDS
    if value >= thresholds[SignalQuality.EXCELLENT]:
        return SignalQuality.EXCELLENT
    if value >= thresholds[SignalQuality.GOOD]:
        return SignalQuality.GOOD
    if value >= thresholds[SignalQuality.FAIR]:
        return SignalQuality.FAIR
    return SignalQuality.POOR


def sinr_to_beep_count(sinr: Optional[float]) -> int:
    """Convert 5G SINR to beep count for audio feedback.

    Higher SINR = more beeps = better signal.
    """
    if sinr is None:
        return 0
    if sinr >= 19:
        return 6
    if sinr >= 18:
        return 5
    if sinr >= 17:
        return 4
    if sinr >= 16:
        return 3
    if sinr >= 14:
        return 2
    if sinr >= 12:
        return 1
    return 0
