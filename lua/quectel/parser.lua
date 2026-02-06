-- AT command response parsing
-- Unified parsing approach for Quectel modem responses

local M = {}

--- Parse a single line of AT response, extracting values after prefix
-- Handles quoted strings and numeric values
-- @param line The response line
-- @param prefix The expected prefix (e.g., "+QENG")
-- @return Table of values, or nil if line doesn't match prefix
function M.parse_line(line, prefix)
    line = line:match("^%s*(.-)%s*$")  -- trim
    if line == "" or line == "OK" or line == "ERROR" then
        return nil
    end

    local expected = prefix .. ":"
    if line:sub(1, #expected) ~= expected then
        return nil
    end

    local content = line:sub(#expected + 1):match("^%s*(.-)%s*$")
    local values = {}

    -- Parse comma-separated values, handling quoted strings
    local pos = 1
    while pos <= #content do
        local char = content:sub(pos, pos)
        if char == '"' then
            -- Quoted string
            local end_quote = content:find('"', pos + 1)
            if end_quote then
                table.insert(values, content:sub(pos + 1, end_quote - 1))
                pos = end_quote + 1
                -- Skip comma
                if content:sub(pos, pos) == "," then
                    pos = pos + 1
                end
            else
                break
            end
        elseif char == "," then
            -- Empty value
            table.insert(values, "")
            pos = pos + 1
        else
            -- Unquoted value
            local comma = content:find(",", pos)
            local val
            if comma then
                val = content:sub(pos, comma - 1)
                pos = comma + 1
            else
                val = content:sub(pos)
                pos = #content + 1
            end
            val = val:match("^%s*(.-)%s*$")  -- trim
            table.insert(values, val)
        end
    end

    return values
end

--- Parse multi-line AT response, yielding all matching lines
-- @param text Full AT response text
-- @param prefix The expected prefix (e.g., "+QENG")
-- @return Iterator function yielding value tables
function M.parse_response(text, prefix)
    local lines = {}
    for line in text:gmatch("[^\r\n]+") do
        table.insert(lines, line)
    end

    local i = 0
    return function()
        while true do
            i = i + 1
            if i > #lines then return nil end
            local values = M.parse_line(lines[i], prefix)
            if values then return values end
        end
    end
end

--- Parse ATI response for device info
-- @param text ATI response
-- @return Table with manufacturer, model, revision
function M.parse_ati(text)
    local lines = {}
    for line in text:gmatch("[^\r\n]+") do
        line = line:match("^%s*(.-)%s*$")
        if line ~= "" and line ~= "OK" then
            table.insert(lines, line)
        end
    end

    return {
        manufacturer = lines[1] or "",
        model = lines[2] or "",
        revision = (lines[3] or ""):gsub("^Revision:%s*", "")
    }
end

--- Parse +QSPN response for operator info
-- @param text AT+QSPN response
-- @return Table with operator name, short name, mcc_mnc
function M.parse_qspn(text)
    for values in M.parse_response(text, "+QSPN") do
        return {
            operator = values[1] or "",
            operator_short = values[2] or "",
            mcc_mnc = values[5] or ""
        }
    end
    return nil
end

--- Parse +QENG="servingcell" response
-- @param text AT+QENG="servingcell" response
-- @return Table with serving cell info (LTE and optionally NR5G-NSA)
function M.parse_serving_cell(text)
    local result = {
        state = nil,
        lte = nil,
        nr5g = nil
    }

    for values in M.parse_response(text, "+QENG") do
        local cell_type = values[1]

        if cell_type == "servingcell" then
            result.state = values[2]

        elseif cell_type == "LTE" then
            result.lte = {
                duplex = values[2],      -- FDD/TDD
                mcc = tonumber(values[3]),
                mnc = tonumber(values[4]),
                cell_id = values[5],     -- hex string
                pci = tonumber(values[6]),
                earfcn = tonumber(values[7]),
                band = tonumber(values[8]),
                bandwidth_dl = tonumber(values[9]),
                bandwidth_ul = tonumber(values[10]),
                tac = values[11],
                rsrp = tonumber(values[12]),
                rsrq = tonumber(values[13]),
                rssi = tonumber(values[14]),
                sinr = tonumber(values[15]),
            }

        elseif cell_type == "NR5G-NSA" then
            result.nr5g = {
                mcc = tonumber(values[2]),
                mnc = tonumber(values[3]),
                pci = tonumber(values[4]),
                rsrp = tonumber(values[5]),
                sinr = tonumber(values[6]),
                rsrq = tonumber(values[7]),
                arfcn = tonumber(values[8]),
                band = tonumber(values[9]),
                bandwidth = tonumber(values[10]),
                scs = tonumber(values[11]),  -- subcarrier spacing
            }
        end
    end

    return result
end

--- Parse +QCAINFO response for carrier aggregation
-- @param text AT+QCAINFO response
-- @return Table with pcc (primary) and scc (list of secondary carriers)
function M.parse_qcainfo(text)
    local result = {
        pcc = nil,
        scc = {}
    }

    for values in M.parse_response(text, "+QCAINFO") do
        local role = values[1]  -- "PCC" or "SCC"
        local band_str = values[4] or ""

        -- Parse band string like "LTE BAND 1" or "NR5G BAND 78"
        local rat, band_num = band_str:match("(%w+) BAND (%d+)")
        local is_nr = (rat == "NR5G")

        local carrier = {
            role = role:lower(),
            earfcn = tonumber(values[2]),
            bandwidth_rb = tonumber(values[3]),
            band = tonumber(band_num),
            rat = is_nr and "nr" or "lte",
            pci = tonumber(values[5]),
            rsrp = tonumber(values[7]),
            rsrq = tonumber(values[8]),
            rssi = tonumber(values[9]),
            sinr = tonumber(values[10]),
        }

        if role == "PCC" then
            result.pcc = carrier
        else
            table.insert(result.scc, carrier)
        end
    end

    return result
end

--- Parse +QENG="neighbourcell" response
-- @param text AT+QENG="neighbourcell" response
-- @return List of neighbour cells
function M.parse_neighbours(text)
    local neighbours = {}

    for values in M.parse_response(text, "+QENG") do
        local cell_type = values[1]

        if cell_type:match("^neighbourcell") then
            local scope = cell_type:match("neighbourcell (%w+)")  -- "intra" or "inter"
            local rat = values[2]  -- "LTE"

            local neighbour = {
                scope = scope,
                rat = rat:lower(),
                earfcn = tonumber(values[3]),
                pci = tonumber(values[4]),
                rsrq = tonumber(values[5]),
                rsrp = tonumber(values[6]),
                rssi = tonumber(values[7]),
            }

            table.insert(neighbours, neighbour)
        end
    end

    return neighbours
end

--- Parse +QNWPREFCFG response for band configuration
-- @param text AT+QNWPREFCFG response
-- @return Table with setting name and value
function M.parse_qnwprefcfg(text)
    for values in M.parse_response(text, "+QNWPREFCFG") do
        local setting = values[1]
        local value = values[2]

        -- Parse band lists like "1:3:7:20"
        if setting:match("band$") and value then
            local bands = {}
            for band in value:gmatch("(%d+)") do
                table.insert(bands, tonumber(band))
            end
            return setting, bands
        end

        return setting, value
    end
    return nil, nil
end

return M
