# Overview

Tools for monitoring and configuring Quectel 5G modems on OpenWRT, originally developed for the GL.INET X-3000 with Quectel RM520N-GL modem and Poynting XPOL-24 directional antenna.

The goal is to extract signal information from the modem to aid accurate pointing of directional antennas, with audio feedback based on 5G SINR values.

## Project Status

**IMPLEMENTED** in Lua:

- `lua/quectel/` - Core library for modem communication and AT command parsing
- `lua/prometheus-collectors/quectel.lua` - Prometheus metrics exporter
- `bin/5g-info` - CLI tool for displaying modem info (table/JSON output)
- `bin/5g-monitor` - ncurses TUI with color-coded signals and beep feedback
- `bin/at` - Simple AT command wrapper
- `bin/5g-lock` - Band and cell locking utility

See `README.md` for usage documentation.

## Key Decisions

- **Language**: Lua (native to OpenWRT, no external deps except luaposix)
- **Modem communication**: Direct serial via luaposix
- **Configuration**: UCI only (`/etc/config/quectel`)
- **Audio feedback**: Terminal bell (`\a`) for SSH compatibility
- **Metrics**: Prometheus exporter for Grafana integration

## Legacy Python Implementation

The original Python implementation is preserved in `legacy/` for reference. See `legacy/README.md` for why we switched to Lua.

## Configuration

UCI config: `/etc/config/quectel`

```
config modem 'modem'
    option device '/dev/ttyUSB2'
    option timeout '2'
    option refresh_interval '5'
    option beeps_enabled '1'
    list lte_bands '1'
    list lte_bands '3'
    list lte_bands '7'
    list lte_bands '20'
    list nr5g_bands '78'
    # Cell locks (earfcn,pci for LTE; pci,arfcn,scs,band for 5G)
    # list lte_cells '275,280'
    # list nr5g_cells '920,648768,15,78'
```

## Sample AT Command Outputs

These sample outputs are used for parser testing:

```
ATI

Quectel
RM520N-GL
Revision: RM520NGLAAR03A03M4G

OK
AT+QSPN

+QSPN: "I TIM","TIM","",0,"22201"

OK
AT+QNWPREFCFG="mode_pref"

+QNWPREFCFG: "mode_pref",AUTO

OK
AT+QNWPREFCFG="nsa_nr5g_band"

+QNWPREFCFG: "nsa_nr5g_band",78

OK
AT+QNWPREFCFG="lte_band"

+QNWPREFCFG: "lte_band",1:3:7:20

OK
AT+QCAINFO

+QCAINFO: "PCC",275,75,"LTE BAND 1",1,280,-99,-14,-67,-4
+QCAINFO: "SCC",1350,100,"LTE BAND 3",1,240,-95,-18,-68,-10,0,-,-
+QCAINFO: "SCC",648768,10,"NR5G BAND 78",920

OK
AT+QENG="servingcell"

+QENG: "servingcell","NOCONN"
+QENG: "LTE","FDD",222,01,328261F,280,275,1,4,4,BE3,-99,-14,-66,7,4,30,-
+QENG: "NR5G-NSA",222,01,920,-96,18,-10,648768,78,10,1

OK
AT+QENG="neighbourcell"

+QENG: "neighbourcell intra","LTE",275,280,-14,-99,-67,-,-,-,-,-,-
+QENG: "neighbourcell intra","LTE",275,34,-20,-105,-76,-,-,-,-,-,-
+QENG: "neighbourcell intra","LTE",275,46,-20,-106,-75,-,-,-,-,-,-
+QENG: "neighbourcell inter","LTE",1350,240,-18,-95,-68,-,-,-,-,-
+QENG: "neighbourcell inter","LTE",1350,427,-14,-94,-69,-,-,-,-,-
+QENG: "neighbourcell inter","LTE",1350,465,-17,-94,-68,-,-,-,-,-
+QENG: "neighbourcell inter","LTE",1350,157,-17,-95,-68,-,-,-,-,-
+QENG: "neighbourcell inter","LTE",1350,47,-18,-96,-69,-,-,-,-,-

OK
```

## SINR vs RSSNR

**Important**: The `AT+QCAINFO` command reports a field that Quectel documentation calls `rssnr`, which is **NOT** the same as SINR from `AT+QENG="servingcell"`.

- **SINR** (from `QENG="servingcell"`): Authoritative Signal-to-Interference-plus-Noise Ratio in dB
- **RSSNR** (from `QCAINFO`): A different metric that can differ significantly from SINR

The parser stores QCAINFO's last numeric field as `rssnr`, and the backfill logic in `modem.lua` populates the `sinr` field from the matching serving cell data. This ensures displayed SINR values are accurate.

## Documentation

- `README.md` - User documentation
- `doc/quectel-rm520n-excerpt.pdf` - Quectel modem AT command reference
