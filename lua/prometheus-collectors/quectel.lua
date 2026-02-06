-- Prometheus collector for Quectel 5G modems
-- Install to /usr/lib/lua/prometheus-collectors/quectel.lua

local quectel = require("quectel")

local M = {}

-- Metric definitions
local METRICS = {
    info = {
        help = "Static information about the modem and operator",
        type = "gauge",
    },
    cell_state = {
        help = "Indicates active connection to a specific cell/tower (1=connected)",
        type = "gauge",
    },
    signal_rsrp_dbm = {
        help = "Reference Signal Received Power in dBm",
        type = "gauge",
    },
    signal_rsrq_db = {
        help = "Reference Signal Received Quality in dB",
        type = "gauge",
    },
    signal_sinr_db = {
        help = "Signal to Interference and Noise Ratio in dB",
        type = "gauge",
    },
    frequency_mhz = {
        help = "Carrier frequency in MHz",
        type = "gauge",
    },
    bandwidth_mhz = {
        help = "Channel bandwidth in MHz",
        type = "gauge",
    },
    tx_power_dbm = {
        help = "Transmission power in dBm",
        type = "gauge",
    },
    neighbour_rsrp_dbm = {
        help = "Neighbour cell signal strength in dBm",
        type = "gauge",
    },
}

-- Format labels for Prometheus
local function format_labels(labels)
    local parts = {}
    for k, v in pairs(labels) do
        if v ~= nil then
            table.insert(parts, string.format('%s="%s"', k, tostring(v)))
        end
    end
    table.sort(parts)  -- consistent ordering
    return "{" .. table.concat(parts, ", ") .. "}"
end

-- Emit a metric line
local function emit(output, name, labels, value)
    if value ~= nil then
        table.insert(output, string.format("modem_%s%s %s", name, format_labels(labels), value))
    end
end

-- Emit metric header (HELP and TYPE)
local function emit_header(output, name)
    local metric = METRICS[name]
    if metric then
        table.insert(output, string.format("# HELP modem_%s %s", name, metric.help))
        table.insert(output, string.format("# TYPE modem_%s %s", name, metric.type))
    end
end

--- Collect metrics from modem
-- @return String with Prometheus-formatted metrics
function M.collect()
    local output = {}
    local modem = quectel.create_modem()

    local ok, status = pcall(function() return modem:get_status() end)
    if not ok or not status then
        -- Modem unavailable - emit nothing
        modem:close()
        return ""
    end

    -- modem_info - static info, always 1
    emit_header(output, "info")
    local info_labels = {
        model = status.device and status.device.model or "unknown",
        revision = status.device and status.device.revision or "",
        imei = status.imei or "",
        operator = status.operator and status.operator.operator or "",
        mcc_mnc = status.operator and status.operator.mcc_mnc or "",
    }
    emit(output, "info", info_labels, 1)
    table.insert(output, "")

    -- Collect serving cells and CA info
    local cells = {}

    -- Primary serving cell from QENG
    if status.serving and status.serving.lte then
        local lte = status.serving.lte
        table.insert(cells, {
            role = "pcc",
            rat = "lte",
            band = lte.band,
            pci = lte.pci,
            enodeb = quectel.extract_enodeb(lte.cell_id),
            cell_id = lte.cell_id,
            rsrp = lte.rsrp,
            rsrq = lte.rsrq,
            sinr = lte.sinr,
            frequency_mhz = lte.frequency_mhz,
            bandwidth_dl_mhz = lte.bandwidth_dl_mhz,
            bandwidth_ul_mhz = lte.bandwidth_ul_mhz,
        })
    end

    -- NR5G-NSA serving cell
    if status.serving and status.serving.nr5g then
        local nr = status.serving.nr5g
        table.insert(cells, {
            role = "scc",  -- NSA is always secondary
            rat = "nr",
            band = nr.band,
            pci = nr.pci,
            enodeb = 0,  -- NR-NSA doesn't report eNodeB
            cell_id = "0",
            rsrp = nr.rsrp,
            rsrq = nr.rsrq,
            sinr = nr.sinr,
            frequency_mhz = nr.frequency_mhz,
            bandwidth_dl_mhz = nr.bandwidth_mhz,
        })
    end

    -- Secondary carriers from QCAINFO
    if status.ca and status.ca.scc then
        for _, scc in ipairs(status.ca.scc) do
            table.insert(cells, {
                role = "scc",
                rat = scc.rat,
                band = scc.band,
                pci = scc.pci,
                enodeb = 0,  -- CA doesn't give us cell ID
                cell_id = "0",
                rsrp = scc.rsrp,
                rsrq = scc.rsrq,
                sinr = scc.sinr,
                frequency_mhz = scc.frequency_mhz,
                bandwidth_dl_mhz = scc.bandwidth_mhz,
            })
        end
    end

    -- Emit cell_state metrics
    emit_header(output, "cell_state")
    for _, cell in ipairs(cells) do
        local labels = {
            role = cell.role,
            rat = cell.rat,
            band = quectel.format_band(cell.band, cell.rat == "nr"),
            pci = cell.pci or 0,
            enodeb = cell.enodeb or 0,
            cell_id = cell.cell_id or "0",
        }
        emit(output, "cell_state", labels, 1)
    end
    table.insert(output, "")

    -- Emit signal metrics
    local signal_labels_fn = function(cell)
        return {
            role = cell.role,
            rat = cell.rat,
            band = quectel.format_band(cell.band, cell.rat == "nr"),
            pci = cell.pci or 0,
        }
    end

    emit_header(output, "signal_rsrp_dbm")
    for _, cell in ipairs(cells) do
        emit(output, "signal_rsrp_dbm", signal_labels_fn(cell), cell.rsrp)
    end
    table.insert(output, "")

    emit_header(output, "signal_rsrq_db")
    for _, cell in ipairs(cells) do
        emit(output, "signal_rsrq_db", signal_labels_fn(cell), cell.rsrq)
    end
    table.insert(output, "")

    emit_header(output, "signal_sinr_db")
    for _, cell in ipairs(cells) do
        emit(output, "signal_sinr_db", signal_labels_fn(cell), cell.sinr)
    end
    table.insert(output, "")

    -- Emit frequency metrics
    emit_header(output, "frequency_mhz")
    for _, cell in ipairs(cells) do
        emit(output, "frequency_mhz", signal_labels_fn(cell), cell.frequency_mhz)
    end
    table.insert(output, "")

    -- Emit bandwidth metrics
    emit_header(output, "bandwidth_mhz")
    for _, cell in ipairs(cells) do
        if cell.bandwidth_dl_mhz then
            local labels = signal_labels_fn(cell)
            labels.direction = "dl"
            emit(output, "bandwidth_mhz", labels, cell.bandwidth_dl_mhz)
        end
        if cell.bandwidth_ul_mhz then
            local labels = signal_labels_fn(cell)
            labels.direction = "ul"
            emit(output, "bandwidth_mhz", labels, cell.bandwidth_ul_mhz)
        end
    end
    table.insert(output, "")

    -- Emit neighbour metrics
    if status.neighbours and #status.neighbours > 0 then
        emit_header(output, "neighbour_rsrp_dbm")
        for _, nb in ipairs(status.neighbours) do
            local labels = {
                rat = nb.rat,
                band = quectel.format_band(quectel.frequency.earfcn_to_mhz(nb.earfcn)),
                pci = nb.pci or 0,
                earfcn = nb.earfcn or 0,
            }
            -- Get band from EARFCN
            if nb.earfcn then
                local _, band = quectel.frequency.earfcn_to_mhz(nb.earfcn)
                labels.band = quectel.format_band(band, false)
            end
            emit(output, "neighbour_rsrp_dbm", labels, nb.rsrp)
        end
        table.insert(output, "")
    end

    modem:close()
    return table.concat(output, "\n")
end

--- Scrape function for prometheus-node-exporter-lua
-- This is the entry point called by the exporter
function M.scrape()
    return M.collect()
end

return M
