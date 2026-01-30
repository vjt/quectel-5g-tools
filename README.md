# quectel-5g-tools

Tools for monitoring and configuring Quectel 5G modems on OpenWRT and Linux systems.

Originally developed for the GL.INET X-3000 with Quectel RM520N-GL modem and Poynting XPOL-24 directional antenna.

## Features

- **5g-info**: CLI tool for displaying modem information (table and JSON output)
- **5g-monitor**: Real-time TUI monitor with color-coded signal quality and audio feedback
- **5g-http.cgi**: CGI script for JSON API (LuCI/uhttpd integration)
- **at**: Simple AT command wrapper
- **force-bands**: Utility to lock modem to specific bands

## Installation

### On OpenWRT

```bash
# From opkg (when published)
opkg install quectel-5g-tools

# From source
cd /path/to/quectel-5g-tools
cp -r src/quectel /usr/lib/python3/
cp bin/* /usr/bin/
cp bin/5g-http.cgi /www/cgi-bin/
mkdir -p /etc/quectel
cp config/quectel.json /etc/quectel/
```

### On other Linux systems

```bash
pip install .
# or for development
pip install -e .
```

## Usage

### 5g-info

Display modem information:

```bash
5g-info                    # Full info with colors
5g-info --json             # JSON output
5g-info --section serving  # Only serving cell
5g-info --no-color         # Plain text
```

### 5g-monitor

Real-time monitoring with ncurses TUI:

```bash
5g-monitor                 # Start monitor
5g-monitor --interval 2    # 2-second refresh
5g-monitor --no-beep       # Disable audio feedback
```

Keyboard controls:
- `q` - Quit
- `r` - Refresh now
- `b` - Toggle beeps
- `j`/`k` - Scroll neighbours

### HTTP API

When installed on OpenWRT with uhttpd:

```bash
curl http://router/cgi-bin/5g-http.cgi?action=status
curl http://router/cgi-bin/5g-http.cgi?action=serving
curl http://router/cgi-bin/5g-http.cgi?action=ca
curl http://router/cgi-bin/5g-http.cgi?action=neighbours
```

### Band locking

```bash
force-bands --lte 1,3,7,20 --nr5g 78 --verify
```

## Configuration

Default config: `/etc/quectel/config.toml`

```toml
[modem]
# Serial device for AT commands (Quectel modems typically use ttyUSB2)
device = "/dev/ttyUSB2"
baudrate = 115200
timeout = 2.0

[monitor]
refresh_interval = 5.0
beep_interval = 0.6
beeps_enabled = true

[bands]
lte = [1, 3, 7, 20]
nr5g = [78]
```

## Signal Quality Thresholds

| Metric | Excellent | Good | Fair | Poor |
|--------|-----------|------|------|------|
| RSRP   | > -80 dBm | > -90 dBm | > -100 dBm | < -100 dBm |
| RSRQ   | > -10 dB  | > -12 dB  | > -15 dB   | < -15 dB   |
| SINR   | > 20 dB   | > 13 dB   | > 0 dB     | < 0 dB     |

## Project Structure

```
quectel-5g-tools/
├── src/quectel/           # Python library
│   ├── models.py          # Data classes
│   ├── parser.py          # AT response parsers
│   ├── modem.py           # Modem backends
│   ├── config.py          # Configuration
│   ├── thresholds.py      # Signal quality thresholds
│   └── frequency.py       # EARFCN conversion
├── bin/                   # Executables
│   ├── 5g-info
│   ├── 5g-monitor
│   ├── 5g-http.cgi
│   ├── at
│   └── force-bands
├── config/                # Default config
├── tests/                 # Unit tests
└── openwrt/               # OpenWRT packaging
```

## License

MIT
