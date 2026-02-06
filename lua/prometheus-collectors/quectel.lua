-- Prometheus collector for Quectel 5G modems
-- Install to /usr/lib/lua/prometheus-collectors/quectel.lua
--
-- Uses get_signal_status() which only makes 2 AT commands:
-- - AT+QENG="servingcell"
-- - AT+QCAINFO
-- This is much lighter than get_status() which makes 6 commands.

local quectel = require("quectel")

local function scrape(metric)
    local modem = quectel.create_modem()

    -- Use lightweight status - only serving cell and CA info (2 AT commands)
    local ok, status = pcall(function() return modem:get_signal_status() end)
    if not ok or not status then
        modem:close()
        return
    end

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
            role = "nsa",  -- NSA is 5G non-standalone
            rat = "nr",
            band = nr.band,
            pci = nr.pci,
            enodeb = 0,
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
                enodeb = 0,
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
    for _, cell in ipairs(cells) do
        metric("modem_cell_state", "gauge", {
            role = cell.role,
            rat = cell.rat,
            band = quectel.format_band(cell.band, cell.rat == "nr"),
            pci = tostring(cell.pci or 0),
            enodeb = tostring(cell.enodeb or 0),
            cell_id = cell.cell_id or "0",
        }, 1)
    end

    -- Emit signal metrics
    for _, cell in ipairs(cells) do
        local labels = {
            role = cell.role,
            rat = cell.rat,
            band = quectel.format_band(cell.band, cell.rat == "nr"),
            pci = tostring(cell.pci or 0),
        }

        if cell.rsrp then
            metric("modem_signal_rsrp_dbm", "gauge", labels, cell.rsrp)
        end
        if cell.rsrq then
            metric("modem_signal_rsrq_db", "gauge", labels, cell.rsrq)
        end
        if cell.sinr then
            metric("modem_signal_sinr_db", "gauge", labels, cell.sinr)
        end
        if cell.frequency_mhz then
            metric("modem_frequency_mhz", "gauge", labels, cell.frequency_mhz)
        end
    end

    -- Emit bandwidth metrics
    for _, cell in ipairs(cells) do
        local base_labels = {
            role = cell.role,
            rat = cell.rat,
            band = quectel.format_band(cell.band, cell.rat == "nr"),
            pci = tostring(cell.pci or 0),
        }

        if cell.bandwidth_dl_mhz then
            local labels = {}
            for k, v in pairs(base_labels) do labels[k] = v end
            labels.direction = "dl"
            metric("modem_bandwidth_mhz", "gauge", labels, cell.bandwidth_dl_mhz)
        end
        if cell.bandwidth_ul_mhz then
            local labels = {}
            for k, v in pairs(base_labels) do labels[k] = v end
            labels.direction = "ul"
            metric("modem_bandwidth_mhz", "gauge", labels, cell.bandwidth_ul_mhz)
        end
    end

    modem:close()
end

return { scrape = scrape }
