# quectel-5g-tools

Tools for monitoring and configuring Quectel 5G modems on OpenWRT.

Originally developed for the GL.INET X-3000 with Quectel RM520N-GL modem and Poynting XPOL-24 directional antenna.

## Features

- **5g-info**: CLI tool for displaying modem information (table and JSON output)
- **5g-monitor**: Real-time TUI monitor with color-coded signal quality and audio feedback
- **Prometheus exporter**: Metrics for Grafana dashboards
- **at**: Simple AT command wrapper
- **force-bands**: Utility to lock modem to specific bands

## Quick Start

Install dependencies on OpenWRT:

```bash
opkg install luaposix
```

Clone the repo and run directly:

```bash
git clone https://github.com/vjt/quectel-5g-tools.git
cd quectel-5g-tools
./bin/5g-info
```

![](doc/5g-info.png)

```bash
./bin/5g-monitor
```

![](doc/5g-monitor.png)

Hear it beep!

## Installation

```bash
# Install Lua library
cp -r lua/quectel /usr/lib/lua/

# Install CLI tools
cp bin/* /usr/bin/

# Install Prometheus collector (optional)
cp lua/prometheus-collectors/quectel.lua /usr/lib/lua/prometheus-collectors/

# Install UCI config
cp config/quectel.uci /etc/config/quectel
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

### Band locking

```bash
force-bands --lte 1:3:7:20 --nr5g 78    # Lock to specific bands
force-bands --verify                     # Show current config
force-bands --reset                      # Reset to all bands
```

### AT commands

```bash
at                          # Run default info commands
at ATI                      # Single command
at AT+CSQ 'AT+CREG?'        # Multiple commands
```

## Prometheus Metrics

Install the collector to `/usr/lib/lua/prometheus-collectors/quectel.lua` and it will be picked up by `prometheus-node-exporter-lua`.

Exported metrics:

| Metric | Labels | Description |
|--------|--------|-------------|
| modem_info | model, revision, imei, operator, mcc_mnc | Static modem info (always 1) |
| modem_cell_state | role, rat, band, pci, enodeb, cell_id | Connected cells (1=active) |
| modem_signal_rsrp_dbm | role, rat, band, pci | Signal strength |
| modem_signal_rsrq_db | role, rat, band, pci | Signal quality |
| modem_signal_sinr_db | role, rat, band, pci | SINR |
| modem_frequency_mhz | role, rat, band, pci | Carrier frequency |
| modem_bandwidth_mhz | role, rat, band, pci, direction | Bandwidth |
| modem_neighbour_rsrp_dbm | rat, band, pci, earfcn | Neighbour cell signals |

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
├── lua/
│   ├── quectel/                    # Core Lua library
│   │   ├── init.lua                # Main API
│   │   ├── modem.lua               # Serial communication
│   │   ├── parser.lua              # AT response parsing
│   │   ├── frequency.lua           # EARFCN conversion
│   │   └── thresholds.lua          # Signal quality
│   └── prometheus-collectors/
│       └── quectel.lua             # Prometheus exporter
├── bin/                            # CLI tools
│   ├── 5g-info
│   ├── 5g-monitor
│   ├── at
│   └── force-bands
├── config/
│   └── quectel.uci                 # UCI config
├── doc/                            # Screenshots
└── legacy/                         # Python implementation (archived)
```

## Dependencies

- **luaposix**: Required for serial I/O and ncurses TUI
- **prometheus-node-exporter-lua**: Optional, for Prometheus metrics

## License

MIT
