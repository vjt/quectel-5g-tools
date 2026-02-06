-- Quectel modem library for OpenWRT
-- Main module providing high-level API

local M = {}

-- Re-export submodules
M.modem = require("quectel.modem")
M.parser = require("quectel.parser")
M.frequency = require("quectel.frequency")
M.thresholds = require("quectel.thresholds")
M.display = require("quectel.display")

-- Module version
M.VERSION = "1.0.0"

--- Load configuration from UCI
-- @return Table with device, timeout, bands, etc.
function M.load_config()
    local config = {
        device = "/dev/ttyUSB2",
        timeout = 2,
        beeps_enabled = true,
        refresh_interval = 5,
        lte_bands = nil,   -- nil = don't change, {} = all bands
        nr5g_bands = nil,
    }

    -- Try to load from UCI
    local ok, uci = pcall(require, "luci.model.uci")
    if ok then
        local cursor = uci.cursor()
        local device = cursor:get("quectel", "@modem[0]", "device")
        local timeout = cursor:get("quectel", "@modem[0]", "timeout")
        local beeps = cursor:get("quectel", "@modem[0]", "beeps_enabled")
        local refresh = cursor:get("quectel", "@modem[0]", "refresh_interval")
        local lte = cursor:get("quectel", "@modem[0]", "lte_bands")
        local nr5g = cursor:get("quectel", "@modem[0]", "nr5g_bands")

        if device then config.device = device end
        if timeout then config.timeout = tonumber(timeout) end
        if beeps then config.beeps_enabled = (beeps == "1") end
        if refresh then config.refresh_interval = tonumber(refresh) end

        -- Band lists come as tables from UCI (list entries)
        if lte and type(lte) == "table" then
            config.lte_bands = {}
            for _, band in ipairs(lte) do
                table.insert(config.lte_bands, tonumber(band))
            end
        end
        if nr5g and type(nr5g) == "table" then
            config.nr5g_bands = {}
            for _, band in ipairs(nr5g) do
                table.insert(config.nr5g_bands, tonumber(band))
            end
        end
    end

    return config
end

--- Create a modem instance with UCI configuration
-- @return Modem instance
function M.create_modem()
    local config = M.load_config()
    return M.modem.new(config.device, config.timeout)
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

return M
