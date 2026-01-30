"""Tests for the frequency module."""

import pytest

from quectel.frequency import (
    earfcn_to_mhz,
    format_frequency,
    format_lte_bandwidth,
    format_nr5g_bandwidth,
    nrarfcn_to_mhz,
)


class TestEarfcnToMhz:
    def test_band1(self):
        freq, band = earfcn_to_mhz(275)
        assert band == 1
        assert 2110 <= freq <= 2170

    def test_band3(self):
        freq, band = earfcn_to_mhz(1350)
        assert band == 3
        assert 1805 <= freq <= 1880

    def test_band7(self):
        freq, band = earfcn_to_mhz(3000)
        assert band == 7
        assert 2620 <= freq <= 2690

    def test_band20(self):
        freq, band = earfcn_to_mhz(6300)
        assert band == 20
        assert 791 <= freq <= 862

    def test_unknown(self):
        freq, band = nrarfcn_to_mhz(999999)
        assert freq is None
        assert band is None


class TestNrarfcnToMhz:
    def test_n78(self):
        freq, band = nrarfcn_to_mhz(648768)
        assert band == 78
        assert 3300 <= freq <= 3800

    def test_unknown(self):
        freq, band = nrarfcn_to_mhz(100000)
        assert freq is None
        assert band is None


class TestFormatFrequency:
    def test_lte(self):
        result = format_frequency(1350, is_5g=False)
        assert "MHz" in result
        assert "B3" in result

    def test_5g(self):
        result = format_frequency(648768, is_5g=True)
        assert "MHz" in result
        assert "N78" in result


class TestFormatBandwidth:
    def test_lte_index(self):
        assert "20 MHz" in format_lte_bandwidth(5)
        assert "10 MHz" in format_lte_bandwidth(3)

    def test_lte_rb(self):
        assert "20 MHz" in format_lte_bandwidth(100, from_qcainfo=True)
        assert "15 MHz" in format_lte_bandwidth(75, from_qcainfo=True)

    def test_nr5g(self):
        assert "80 MHz" in format_nr5g_bandwidth(10)
        assert "100 MHz" in format_nr5g_bandwidth(12)
