-- Quectel modem library for OpenWRT
-- Main module providing high-level API

local M = {}

-- Re-export submodules
M.modem = require("quectel.modem")
M.parser = require("quectel.parser")
M.frequency = require("quectel.frequency")
M.thresholds = require("quectel.thresholds")
M.display = require("quectel.display")
M.utils = require("quectel.utils")

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
        lte_cells = nil,   -- nil = don't change, {} = clear locks
        nr5g_cells = nil,
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

        -- Cell lock lists (earfcn,pci pairs for LTE; pci,arfcn,scs,band for 5G)
        local lte_cells = cursor:get("quectel", "@modem[0]", "lte_cells")
        local nr5g_cells = cursor:get("quectel", "@modem[0]", "nr5g_cells")

        if lte_cells and type(lte_cells) == "table" then
            config.lte_cells = {}
            for _, entry in ipairs(lte_cells) do
                local earfcn, pci = entry:match("^(%d+),(%d+)$")
                if earfcn and pci then
                    table.insert(config.lte_cells, {
                        earfcn = tonumber(earfcn),
                        pci = tonumber(pci),
                    })
                end
            end
        end

        if nr5g_cells and type(nr5g_cells) == "table" then
            config.nr5g_cells = {}
            for _, entry in ipairs(nr5g_cells) do
                local pci, arfcn, scs, band = entry:match("^(%d+),(%d+),(%d+),(%d+)$")
                if pci and arfcn and scs and band then
                    table.insert(config.nr5g_cells, {
                        pci = tonumber(pci),
                        arfcn = tonumber(arfcn),
                        scs = tonumber(scs),
                        band = tonumber(band),
                    })
                end
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

-- Re-export common utility functions for convenience
M.format_band = M.utils.format_band
M.format_cell_id = M.utils.format_cell_id
M.extract_enodeb = M.utils.extract_enodeb

return M
