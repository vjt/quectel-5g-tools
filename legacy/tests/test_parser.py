"""Tests for the parser module."""

import pytest

from quectel.parser import (
    parse_ati,
    parse_qcainfo,
    parse_qeng_neighbourcell,
    parse_qeng_servingcell,
    parse_qnwprefcfg,
    parse_qspn,
    parse_response,
)


class TestParseResponse:
    def test_basic(self):
        response = '+QSPN: "I TIM","TIM","",0,"22201"\n\nOK'
        results = list(parse_response(response, "+QSPN"))
        assert len(results) == 1
        assert results[0] == ["I TIM", "TIM", "", "0", "22201"]

    def test_multiple_lines(self):
        response = """+QENG: "LTE","FDD",222,01
+QENG: "NR5G-NSA",222,01

OK"""
        results = list(parse_response(response, "+QENG"))
        assert len(results) == 2

    def test_skips_empty_and_ok(self):
        response = "\n\n+TEST: a,b,c\n\nOK\n"
        results = list(parse_response(response, "+TEST"))
        assert len(results) == 1
        assert results[0] == ["a", "b", "c"]

    def test_strips_quotes(self):
        response = '+TEST: "quoted","also quoted",unquoted\nOK'
        results = list(parse_response(response, "+TEST"))
        assert results[0] == ["quoted", "also quoted", "unquoted"]


class TestParseAti:
    def test_basic(self):
        response = """Quectel
RM520N-GL
Revision: RM520NGLAAR03A03M4G

OK"""
        info = parse_ati(response)
        assert info is not None
        assert info.manufacturer == "Quectel"
        assert info.model == "RM520N-GL"
        assert info.revision == "RM520NGLAAR03A03M4G"

    def test_empty(self):
        assert parse_ati("") is None
        assert parse_ati("OK") is None


class TestParseQspn:
    def test_basic(self):
        response = '+QSPN: "I TIM","TIM","",0,"22201"\n\nOK'
        info = parse_qspn(response)
        assert info is not None
        assert info.full_name == "I TIM"
        assert info.short_name == "TIM"
        assert info.mcc == 222
        assert info.mnc == 1
        assert info.mcc_mnc == "222-01"

    def test_empty(self):
        assert parse_qspn("") is None


class TestParseQengServingcell:
    def test_lte_only(self):
        response = """+QENG: "servingcell","NOCONN"
+QENG: "LTE","FDD",222,01,328261F,280,275,1,4,4,BE3,-99,-14,-66,7,4,30,-

OK"""
        lte, nr5g = parse_qeng_servingcell(response)

        assert lte is not None
        assert lte.mode == "FDD"
        assert lte.mcc == 222
        assert lte.mnc == 1
        assert lte.pci == 280
        assert lte.earfcn == 275
        assert lte.band == 1
        assert lte.rsrp == -99
        assert lte.rsrq == -14
        assert lte.sinr == 7

        assert nr5g is None

    def test_lte_and_5g(self):
        response = """+QENG: "servingcell","NOCONN"
+QENG: "LTE","FDD",222,01,328261F,280,275,1,4,4,BE3,-99,-14,-66,7,4,30,-
+QENG: "NR5G-NSA",222,01,920,-96,18,-10,648768,78,10,1

OK"""
        lte, nr5g = parse_qeng_servingcell(response)

        assert lte is not None
        assert lte.band == 1

        assert nr5g is not None
        assert nr5g.pci == 920
        assert nr5g.rsrp == -96
        assert nr5g.sinr == 18
        assert nr5g.rsrq == -10
        assert nr5g.arfcn == 648768
        assert nr5g.band == 78


class TestParseQcainfo:
    def test_mixed(self):
        response = """+QCAINFO: "PCC",275,75,"LTE BAND 1",1,280,-99,-14,-67,-4
+QCAINFO: "SCC",1350,100,"LTE BAND 3",1,240,-95,-18,-68,-10,0,-,-
+QCAINFO: "SCC",648768,10,"NR5G BAND 78",920

OK"""
        components = parse_qcainfo(response)

        assert len(components) == 3

        pcc = components[0]
        assert pcc.component_type == "PCC"
        assert pcc.band_name == "LTE BAND 1"
        assert pcc.pci == 280
        assert pcc.rsrp == -99

        scc_lte = components[1]
        assert scc_lte.component_type == "SCC"
        assert scc_lte.band_name == "LTE BAND 3"

        scc_5g = components[2]
        assert scc_5g.component_type == "SCC"
        assert scc_5g.band_name == "NR5G BAND 78"
        assert scc_5g.is_5g


class TestParseQengNeighbourcell:
    def test_basic(self):
        response = """+QENG: "neighbourcell intra","LTE",275,280,-14,-99,-67,-,-,-,-,-,-
+QENG: "neighbourcell intra","LTE",275,34,-20,-105,-76,-,-,-,-,-,-
+QENG: "neighbourcell inter","LTE",1350,240,-18,-95,-68,-,-,-,-,-

OK"""
        cells = parse_qeng_neighbourcell(response)

        assert len(cells) == 3

        assert cells[0].cell_type == "intra"
        assert cells[0].earfcn == 275
        assert cells[0].pci == 280

        assert cells[2].cell_type == "inter"
        assert cells[2].earfcn == 1350


class TestParseQnwprefcfg:
    def test_basic(self):
        response = """+QNWPREFCFG: "mode_pref",AUTO

OK"""
        config = parse_qnwprefcfg(response)
        assert config["mode_pref"] == "AUTO"

    def test_bands(self):
        response = '+QNWPREFCFG: "lte_band",1:3:7:20\n\nOK'
        config = parse_qnwprefcfg(response)
        assert config["lte_band"] == "1:3:7:20"
