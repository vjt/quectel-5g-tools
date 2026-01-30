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

    def test_band2(self):
        freq, band = earfcn_to_mhz(900)
        assert band == 2
        assert 1930 <= freq <= 1990

    def test_band3(self):
        freq, band = earfcn_to_mhz(1350)
        assert band == 3
        assert 1805 <= freq <= 1880

    def test_band5(self):
        freq, band = earfcn_to_mhz(2500)
        assert band == 5
        assert 869 <= freq <= 894

    def test_band7(self):
        freq, band = earfcn_to_mhz(3000)
        assert band == 7
        assert 2620 <= freq <= 2690

    def test_band8(self):
        freq, band = earfcn_to_mhz(3600)
        assert band == 8
        assert 925 <= freq <= 960

    def test_band12(self):
        freq, band = earfcn_to_mhz(5100)
        assert band == 12
        assert 729 <= freq <= 746

    def test_band20(self):
        freq, band = earfcn_to_mhz(6300)
        assert band == 20
        assert 791 <= freq <= 821

    def test_band28(self):
        freq, band = earfcn_to_mhz(9400)
        assert band == 28
        assert 758 <= freq <= 803

    def test_band38_tdd(self):
        freq, band = earfcn_to_mhz(38000)
        assert band == 38
        assert 2570 <= freq <= 2620

    def test_band41_tdd(self):
        freq, band = earfcn_to_mhz(40000)
        assert band == 41
        assert 2496 <= freq <= 2690

    def test_band66(self):
        freq, band = earfcn_to_mhz(66900)
        assert band == 66
        assert 2110 <= freq <= 2200

    def test_band71(self):
        freq, band = earfcn_to_mhz(68700)
        assert band == 71
        assert 617 <= freq <= 652

    def test_unknown(self):
        freq, band = earfcn_to_mhz(999999)
        assert freq is None
        assert band is None


class TestNrarfcnToMhz:
    def test_n1(self):
        # n1 UL: 1920-1980 MHz, ARFCN 384000-396000
        freq, band = nrarfcn_to_mhz(390000)
        assert band == 1
        assert 1920 <= freq <= 1980

    def test_n3(self):
        # n3 UL: 1710-1785 MHz, use ARFCN > 356000 to avoid n86 overlap
        freq, band = nrarfcn_to_mhz(356500)
        assert band == 3
        assert 1780 <= freq <= 1785

    def test_n41(self):
        freq, band = nrarfcn_to_mhz(520000)
        assert band == 41
        assert 2496 <= freq <= 2690

    def test_n77(self):
        # Use ARFCN > 653333 to avoid overlap with n78 (620000-653333)
        freq, band = nrarfcn_to_mhz(660000)
        assert band == 77
        assert 3300 <= freq <= 4200

    def test_n78(self):
        freq, band = nrarfcn_to_mhz(648768)
        assert band == 78
        assert 3300 <= freq <= 3800

    def test_n79(self):
        freq, band = nrarfcn_to_mhz(710000)
        assert band == 79
        assert 4400 <= freq <= 5000

    def test_n257_mmwave(self):
        # n257: 27.5-28.35 GHz, ARFCN 2054166-2104165
        freq, band = nrarfcn_to_mhz(2080000)
        assert band == 257
        assert 26500 <= freq <= 29500

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
        assert "n78" in result

    def test_unknown_lte(self):
        result = format_frequency(999999, is_5g=False)
        assert "Unknown" in result

    def test_unknown_5g(self):
        result = format_frequency(100000, is_5g=True)
        assert "Unknown" in result


class TestFormatBandwidth:
    def test_lte_index(self):
        assert "20 MHz" in format_lte_bandwidth(5)
        assert "10 MHz" in format_lte_bandwidth(3)
        assert "1.4 MHz" in format_lte_bandwidth(0)

    def test_lte_rb(self):
        assert "20 MHz" in format_lte_bandwidth(100, from_qcainfo=True)
        assert "15 MHz" in format_lte_bandwidth(75, from_qcainfo=True)
        assert "1.4 MHz" in format_lte_bandwidth(6, from_qcainfo=True)

    def test_nr5g(self):
        assert "80 MHz" in format_nr5g_bandwidth(10)
        assert "100 MHz" in format_nr5g_bandwidth(12)
        assert "5 MHz" in format_nr5g_bandwidth(0)
        assert "200 MHz" in format_nr5g_bandwidth(13)
        assert "400 MHz" in format_nr5g_bandwidth(14)
