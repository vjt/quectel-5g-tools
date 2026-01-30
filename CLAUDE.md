# Overview

This project provides tools for monitoring and configuring Quectel 5G modems, originally developed for the GL.INET X-3000 with Quectel RM520N-GL modem and Poynting XPOL-24 directional antenna.

The goal is to extract signal information from the modem to aid accurate pointing of directional antennas, with audio feedback based on 5G SINR values.

## Project Status

**IMPLEMENTED** - The following components have been created:

- `src/quectel/` - Python library for modem communication and AT command parsing
- `bin/5g-info` - CLI tool for displaying modem info (table/JSON output)
- `bin/5g-monitor` - ncurses TUI with color-coded signals and beep feedback
- `bin/5g-http.cgi` - CGI script for JSON API
- `bin/at` - Simple AT command wrapper
- `bin/force-bands` - Band locking utility

See `README.md` for usage documentation.

## Key Decisions

- **Language**: Python 3 (chosen for portability beyond OpenWRT and rich ncurses support)
- **Modem communication**: Supports both `gl_modem` wrapper and direct pyserial
- **Audio feedback**: Terminal bell (`\a`) for SSH compatibility
- **HTTP**: uhttpd CGI integration, no auth in v1

## Legacy Files

The following files are from the original prototype and can be removed:

- `5g-monitor.py` - replaced by `bin/5g-monitor`
- `5g-scan.py` - functionality merged into `bin/5g-monitor`

## Configuration

Default config: `/etc/quectel/config.json` or `config/quectel.json`

On OpenWRT, UCI config (`uci get quectel.@modem[0].*`) overlays JSON settings.

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

## Documentation

- `README.md` - User documentation
- `quectel-rm520n-excerpt.pdf` - Quectel modem AT command reference
