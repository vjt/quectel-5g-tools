-- Prometheus collector for Quectel 5G modems
-- Install to /usr/lib/lua/prometheus-collectors/quectel.lua
--
-- Uses get_signal_status() which only makes 2 AT commands:
-- - AT+QENG="servingcell"
-- - AT+QCAINFO
-- This is much lighter than get_status() which makes 6 commands.
--
-- Compatible with prometheus-node-exporter-lua 2024.06.16 (GL.iNET firmware)
-- The metric() function returns an outputter - call it once per metric name,
-- then use the returned function for each value.

local quectel = require("quectel")

local function scrape()
    -- Use global metric function from prometheus-node-exporter-lua
    if not metric then
        error("No metric function available - check prometheus-node-exporter-lua installation")
    end

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
            role = "nsa",
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
    -- Skip NR5G entries that duplicate serving.nr5g (same PCI and band)
    local nr5g_pci = status.serving and status.serving.nr5g and status.serving.nr5g.pci
    local nr5g_band = status.serving and status.serving.nr5g and status.serving.nr5g.band

    if status.ca and status.ca.scc then
        for _, scc in ipairs(status.ca.scc) do
            -- Skip if this is a duplicate of the serving NR5G cell
            local is_duplicate = (scc.rat == "nr" and scc.pci == nr5g_pci and scc.band == nr5g_band)
            if not is_duplicate then
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
    end

    -- Create metric outputters (each call to metric() prints TYPE once)
    local cell_state = metric("modem_cell_state", "gauge")
    local signal_rsrp = metric("modem_signal_rsrp_dbm", "gauge")
    local signal_rsrq = metric("modem_signal_rsrq_db", "gauge")
    local signal_sinr = metric("modem_signal_sinr_db", "gauge")
    local freq = metric("modem_frequency_mhz", "gauge")
    local bw = metric("modem_bandwidth_mhz", "gauge")

    -- Emit all metrics
    for _, cell in ipairs(cells) do
        local base_labels = {
            role = cell.role,
            rat = cell.rat,
            band = quectel.format_band(cell.band, cell.rat == "nr"),
            pci = tostring(cell.pci or 0),
        }

        -- Cell state (with extra labels)
        local state_labels = {
            role = cell.role,
            rat = cell.rat,
            band = quectel.format_band(cell.band, cell.rat == "nr"),
            pci = tostring(cell.pci or 0),
            enodeb = tostring(cell.enodeb or 0),
            cell_id = cell.cell_id or "0",
        }
        cell_state(state_labels, 1)

        -- Signal metrics
        if cell.rsrp then
            signal_rsrp(base_labels, cell.rsrp)
        end
        if cell.rsrq then
            signal_rsrq(base_labels, cell.rsrq)
        end
        if cell.sinr then
            signal_sinr(base_labels, cell.sinr)
        end
        if cell.frequency_mhz then
            freq(base_labels, cell.frequency_mhz)
        end

        -- Bandwidth metrics
        if cell.bandwidth_dl_mhz then
            local dl_labels = {}
            for k, v in pairs(base_labels) do dl_labels[k] = v end
            dl_labels.direction = "dl"
            bw(dl_labels, cell.bandwidth_dl_mhz)
        end
        if cell.bandwidth_ul_mhz then
            local ul_labels = {}
            for k, v in pairs(base_labels) do ul_labels[k] = v end
            ul_labels.direction = "ul"
            bw(ul_labels, cell.bandwidth_ul_mhz)
        end
    end

    modem:close()
end

return { scrape = scrape }
