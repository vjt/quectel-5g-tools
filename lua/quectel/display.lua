-- Display utilities for Quectel modem tools
-- Shared presentation logic for 5g-info and 5g-monitor

local M = {}

-- Load dependencies
local frequency = require("quectel.frequency")
local thresholds = require("quectel.thresholds")
local utils = require("quectel.utils")

-- ANSI escape codes
M.ESC = "\027"
M.CLEAR = M.ESC .. "[2J"
M.HOME = M.ESC .. "[H"
M.HIDE_CURSOR = M.ESC .. "[?25l"
M.SHOW_CURSOR = M.ESC .. "[?25h"

M.Colors = {
    RESET = M.ESC .. "[0m",
    BOLD = M.ESC .. "[1m",
    RED = M.ESC .. "[91m",
    GREEN = M.ESC .. "[92m",
    YELLOW = M.ESC .. "[93m",
    BLUE = M.ESC .. "[94m",
    CYAN = M.ESC .. "[96m",
    WHITE = M.ESC .. "[97m",
}

-- State
local use_color = true

--- Enable or disable color output
function M.set_color(enabled)
    use_color = enabled
end

--- Get color code (respects use_color setting)
function M.color(col)
    if use_color then return col else return "" end
end

--- Get color for signal quality level
function M.quality_color(quality)
    if quality == thresholds.EXCELLENT then return M.Colors.CYAN end
    if quality == thresholds.GOOD then return M.Colors.GREEN end
    if quality == thresholds.FAIR then return M.Colors.YELLOW end
    if quality == thresholds.POOR then return M.Colors.RED end
    return M.Colors.WHITE
end

--- Format a signal value with optional quality indicator
-- @param value Signal value (number or nil)
-- @param quality Quality level (from thresholds)
-- @param show_label If true, show quality label in parentheses
-- @return Formatted string
function M.format_signal(value, quality, show_label)
    if not value then return "-" end

    local col = M.color(M.quality_color(quality))
    local reset = M.color(M.Colors.RESET)

    if show_label and quality and quality ~= "" then
        return string.format("%s%d%s (%s)", col, value, reset, quality)
    else
        return string.format("%s%d%s", col, value, reset)
    end
end

--- Print device info section
function M.print_device_info(status)
    if not status.device then
        print("Device: unavailable")
        return
    end
    print(string.format("Device: %s %s (%s)",
        status.device.manufacturer or "?",
        status.device.model or "?",
        status.device.revision or "?"))
    if status.imei then
        print(string.format("IMEI: %s", status.imei))
    end
end

--- Print network info section
function M.print_network_info(status)
    if not status.operator then
        print("Network: unavailable")
        return
    end
    print(string.format("Network: %s (%s)",
        status.operator.operator or "?",
        status.operator.mcc_mnc or "?"))
end

--- Print serving cell section
-- @param status Modem status
function M.print_serving_cell(status)
    if not status.serving then
        print("\nServing cell: no signal")
        return
    end

    local lte = status.serving.lte
    local nr = status.serving.nr5g

    if lte then
        local rsrp_q = thresholds.rsrp_quality(lte.rsrp)
        local rsrq_q = thresholds.rsrq_quality(lte.rsrq)
        local sinr_q = thresholds.sinr_quality(lte.sinr)
        local enodeb = utils.extract_enodeb(lte.cell_id) or "?"

        print(string.format("\n%s[LTE - Band %s]%s %s | eNodeB: %s | PCI: %s | TAC: %s",
            M.color(M.Colors.BLUE), lte.band or "?", M.color(M.Colors.RESET),
            lte.duplex or "?", enodeb, lte.pci or "?", lte.tac or "?"))

        print(string.format("  RSRP: %s dBm | RSRQ: %s dB | SINR: %s dB",
            M.format_signal(lte.rsrp, rsrp_q),
            M.format_signal(lte.rsrq, rsrq_q),
            M.format_signal(lte.sinr, sinr_q)))

        local freq_str = frequency.format_frequency(lte.arfcn or 0, false)
        local dl_bw = frequency.format_bandwidth(lte.bandwidth_dl_mhz)
        local ul_bw = frequency.format_bandwidth(lte.bandwidth_ul_mhz)
        print(string.format("  Freq: %s | BW: DL %s / UL %s", freq_str, dl_bw, ul_bw))
    end

    if nr then
        local rsrp_q = thresholds.rsrp_quality(nr.rsrp)
        local rsrq_q = thresholds.rsrq_quality(nr.rsrq)
        local sinr_q = thresholds.sinr_quality(nr.sinr)

        print("")
        print(string.format("%s[5G-NSA - Band n%s]%s PCI: %s",
            M.color(M.Colors.GREEN), nr.band or "?", M.color(M.Colors.RESET),
            nr.pci or "?"))

        print(string.format("  RSRP: %s dBm | RSRQ: %s dB | SINR: %s dB",
            M.format_signal(nr.rsrp, rsrp_q),
            M.format_signal(nr.rsrq, rsrq_q),
            M.format_signal(nr.sinr, sinr_q)))

        local freq_str = frequency.format_frequency(nr.arfcn or 0, true)
        local bw = frequency.format_bandwidth(nr.bandwidth_mhz)
        print(string.format("  Freq: %s | BW: %s", freq_str, bw))
    end

    if not lte and not nr then
        print("\nServing cell: no signal")
    end
end

--- Print carrier aggregation section
-- @param status Modem status
function M.print_carrier_aggregation(status)
    if not status.ca or (not status.ca.pcc and #status.ca.scc == 0) then
        print("\nCarrier Aggregation: none")
        return
    end

    print(string.format("\n%sCarrier Aggregation:%s", M.color(M.Colors.BOLD), M.color(M.Colors.RESET)))

    local function print_carrier(carrier)
        local is_nr = carrier.rat == "5g"
        local band_name = utils.format_band(carrier.band, is_nr)
        local rsrp_q = thresholds.rsrp_quality(carrier.rsrp)
        local sinr_q = thresholds.sinr_quality(carrier.sinr)

        local col = carrier.role == "pcc" and M.Colors.BLUE or M.Colors.CYAN

        local bw = frequency.format_bandwidth(carrier.bandwidth_mhz)
        local freq_str = frequency.format_frequency(carrier.arfcn or 0, is_nr)
        print(string.format("  %s%-3s%s %-8s | PCI %3s | RSRP %s | SINR %s | %7s | %s",
            M.color(col), carrier.role:upper(), M.color(M.Colors.RESET),
            band_name, carrier.pci or "-",
            M.format_signal(carrier.rsrp, rsrp_q),
            M.format_signal(carrier.sinr, sinr_q),
            bw, freq_str))
    end

    if status.ca.pcc then
        print_carrier(status.ca.pcc)
    end

    for _, scc in ipairs(status.ca.scc) do
        print_carrier(scc)
    end
end

--- Print neighbour cells section
-- @param status Modem status
-- @param max_rows Maximum rows to display (nil for all)
function M.print_neighbours(status, max_rows)
    if not status.neighbours or #status.neighbours == 0 then
        print("\nNeighbour Cells: none")
        return
    end

    -- Sort by RSRP descending (strongest first)
    local sorted = {}
    for _, nb in ipairs(status.neighbours) do
        table.insert(sorted, nb)
    end
    table.sort(sorted, function(a, b)
        local rsrp_a = a.rsrp or -999
        local rsrp_b = b.rsrp or -999
        return rsrp_a > rsrp_b
    end)

    print(string.format("\n%sNeighbour Cells:%s", M.color(M.Colors.BOLD), M.color(M.Colors.RESET)))

    local count = 0
    for _, nb in ipairs(sorted) do
        if max_rows and count >= max_rows then
            print(string.format("  ... and %d more", #sorted - count))
            break
        end

        local rsrp_q = thresholds.rsrp_quality(nb.rsrp)
        local freq_str = frequency.format_frequency(nb.arfcn or 0, false)

        print(string.format("  %-3s %-18s | PCI %3s | RSRP %s | (%s)",
            nb.rat:upper(), freq_str, nb.pci or "-",
            M.format_signal(nb.rsrp, rsrp_q),
            nb.scope or "?"))

        count = count + 1
    end
end

--- Emit beeps with delay between them
-- @param count Number of beeps (default 1)
-- @param delay Delay between beeps in seconds (default 0.6)
-- @param sleep_fn Optional custom sleep function (for interruptible sleep)
-- @param check_fn Optional function that returns false to abort beeping
function M.beep(count, delay, sleep_fn, check_fn)
    count = count or 1
    delay = delay or 0.6
    sleep_fn = sleep_fn or function(s) os.execute("sleep " .. s) end
    check_fn = check_fn or function() return true end

    for i = 1, count do
        if not check_fn() then break end
        io.write("\a")
        io.flush()
        if i < count and check_fn() then
            sleep_fn(delay)
        end
    end
end

--- Get SINR value from status (prefers 5G over LTE)
function M.get_sinr(status)
    if not status.serving then return nil end

    if status.serving.nr5g and status.serving.nr5g.sinr then
        return status.serving.nr5g.sinr
    elseif status.serving.lte and status.serving.lte.sinr then
        return status.serving.lte.sinr
    end

    return nil
end

--- Simple JSON encoder
function M.to_json(value, indent)
    indent = indent or 0
    local t = type(value)

    if t == "nil" then
        return "null"
    elseif t == "boolean" then
        return value and "true" or "false"
    elseif t == "number" then
        return tostring(value)
    elseif t == "string" then
        return string.format('"%s"', value:gsub('"', '\\"'))
    elseif t == "table" then
        -- Check if array
        local is_array = #value > 0 or next(value) == nil
        if is_array then
            local items = {}
            for _, v in ipairs(value) do
                table.insert(items, M.to_json(v, indent + 2))
            end
            if #items == 0 then return "[]" end
            return "[\n" .. string.rep(" ", indent + 2) ..
                   table.concat(items, ",\n" .. string.rep(" ", indent + 2)) ..
                   "\n" .. string.rep(" ", indent) .. "]"
        else
            local items = {}
            for k, v in pairs(value) do
                table.insert(items, string.format('"%s": %s', k, M.to_json(v, indent + 2)))
            end
            table.sort(items)
            if #items == 0 then return "{}" end
            return "{\n" .. string.rep(" ", indent + 2) ..
                   table.concat(items, ",\n" .. string.rep(" ", indent + 2)) ..
                   "\n" .. string.rep(" ", indent) .. "}"
        end
    end
    return "null"
end

return M
