-- Utility functions for Quectel modem library

local M = {}

-- Load frequency module for enrichment
local frequency = require("quectel.frequency")

-- Load posix.time for sleep (optional, graceful fallback)
local posix_time_ok, posix_time = pcall(require, "posix.time")

--- Sleep for specified seconds using nanosleep
-- Falls back to os.execute if posix.time unavailable
-- @param seconds Number of seconds to sleep (can be fractional)
function M.sleep(seconds)
    if posix_time_ok then
        local sec = math.floor(seconds)
        local nsec = math.floor((seconds - sec) * 1e9)
        posix_time.nanosleep({tv_sec = sec, tv_nsec = nsec})
    else
        os.execute("sleep " .. seconds)
    end
end

--- Format band string (e.g., "B1" or "n78")
-- @param band Band number
-- @param is_nr True for NR bands
-- @return Formatted string
function M.format_band(band, is_nr)
    if not band then return "?" end
    if is_nr then
        return "n" .. band
    else
        return "B" .. band
    end
end

--- Format cell ID as hex
-- @param cell_id Cell ID (may be hex string already)
-- @return Hex string
function M.format_cell_id(cell_id)
    if not cell_id then return "?" end
    if type(cell_id) == "number" then
        return string.format("%X", cell_id)
    end
    return cell_id
end

--- Extract eNodeB ID from cell ID
-- For LTE, eNodeB is upper 20 bits of 28-bit cell ID
-- @param cell_id Cell ID (hex string or number)
-- @return eNodeB ID as number
function M.extract_enodeb(cell_id)
    if not cell_id then return nil end

    local num
    if type(cell_id) == "string" then
        num = tonumber(cell_id, 16)
    else
        num = cell_id
    end

    if not num then return nil end

    -- eNodeB is bits 8-27 (upper 20 bits of 28-bit cell ID)
    return math.floor(num / 256)
end

--- Check if two cells are the same based on PCI and ARFCN
-- @param a First cell (must have pci and arfcn fields)
-- @param b Second cell (must have pci and arfcn fields)
-- @return true if cells match by PCI or ARFCN
function M.same_cell(a, b)
    if not a or not b then return false end

    local pci_match = a.pci and b.pci and a.pci == b.pci
    local arfcn_match = a.arfcn and b.arfcn and a.arfcn == b.arfcn

    return pci_match or arfcn_match
end

--- Add frequency and bandwidth info to a serving cell structure
-- Modifies the status table in place
-- @param status Status table with serving and ca fields
function M.add_frequency_info(status)
    -- Enrich LTE serving cell
    if status.serving and status.serving.lte then
        local lte = status.serving.lte
        if lte.arfcn then
            lte.frequency_mhz = frequency.earfcn_to_mhz(lte.arfcn)
        end
        if lte.bandwidth_dl then
            lte.bandwidth_dl_mhz = frequency.lte_bandwidth_mhz(lte.bandwidth_dl)
        end
        if lte.bandwidth_ul then
            lte.bandwidth_ul_mhz = frequency.lte_bandwidth_mhz(lte.bandwidth_ul)
        end
    end

    -- Enrich NR5G serving cell
    if status.serving and status.serving.nr5g then
        local nr = status.serving.nr5g
        if nr.arfcn then
            nr.frequency_mhz = frequency.nrarfcn_to_mhz(nr.arfcn)
        end
        if nr.bandwidth then
            nr.bandwidth_mhz = frequency.nr5g_bandwidth_mhz(nr.bandwidth)
        end
    end

    -- Enrich carrier aggregation info
    if status.ca then
        -- Helper to enrich a single carrier
        local function enrich_carrier(carrier)
            if carrier.arfcn then
                if carrier.rat == "5g" then
                    carrier.frequency_mhz = frequency.nrarfcn_to_mhz(carrier.arfcn)
                else
                    carrier.frequency_mhz = frequency.earfcn_to_mhz(carrier.arfcn)
                end
            end
            if carrier.bandwidth_rb then
                carrier.bandwidth_mhz = frequency.lte_bandwidth_mhz(carrier.bandwidth_rb, true)
            end
        end

        if status.ca.pcc then
            enrich_carrier(status.ca.pcc)
        end

        for _, scc in ipairs(status.ca.scc or {}) do
            enrich_carrier(scc)
        end
    end
end

return M
