"""Tests for the thresholds module."""

import pytest

from quectel.thresholds import (
    SignalQuality,
    classify_rsrp,
    classify_rsrq,
    classify_sinr,
    sinr_to_beep_count,
)


class TestClassifyRsrp:
    def test_excellent(self):
        assert classify_rsrp(-75) == SignalQuality.EXCELLENT
        assert classify_rsrp(-80) == SignalQuality.EXCELLENT

    def test_good(self):
        assert classify_rsrp(-85) == SignalQuality.GOOD
        assert classify_rsrp(-90) == SignalQuality.GOOD

    def test_fair(self):
        assert classify_rsrp(-95) == SignalQuality.FAIR
        assert classify_rsrp(-100) == SignalQuality.FAIR

    def test_poor(self):
        assert classify_rsrp(-105) == SignalQuality.POOR
        assert classify_rsrp(-120) == SignalQuality.POOR

    def test_unknown(self):
        assert classify_rsrp(None) == SignalQuality.UNKNOWN


class TestClassifyRsrq:
    def test_excellent(self):
        assert classify_rsrq(-5) == SignalQuality.EXCELLENT

    def test_good(self):
        assert classify_rsrq(-11) == SignalQuality.GOOD

    def test_fair(self):
        assert classify_rsrq(-14) == SignalQuality.FAIR

    def test_poor(self):
        assert classify_rsrq(-18) == SignalQuality.POOR


class TestClassifySinr:
    def test_lte_excellent(self):
        assert classify_sinr(25, is_5g=False) == SignalQuality.EXCELLENT

    def test_5g_good(self):
        assert classify_sinr(15, is_5g=True) == SignalQuality.GOOD


class TestSinrToBeepCount:
    def test_excellent(self):
        assert sinr_to_beep_count(19) == 6
        assert sinr_to_beep_count(20) == 6

    def test_very_good(self):
        assert sinr_to_beep_count(18) == 5
        assert sinr_to_beep_count(17) == 4
        assert sinr_to_beep_count(16) == 3

    def test_good(self):
        assert sinr_to_beep_count(15) == 2
        assert sinr_to_beep_count(14) == 2

    def test_fair(self):
        assert sinr_to_beep_count(12) == 1

    def test_poor(self):
        assert sinr_to_beep_count(10) == 0
        assert sinr_to_beep_count(0) == 0
        assert sinr_to_beep_count(None) == 0
