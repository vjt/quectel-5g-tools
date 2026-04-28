-- quectel.uci — single UCI accessor for everything quectel-5g-tools.
--
-- Wraps libuci-lua (the canonical OpenWrt C binding, present on every
-- router that has uci) and falls back to luci.model.uci on hosts that
-- happen to have luci-base installed instead. All callers go through
-- this module so we don't have a popen-uci shellout in 5g-led-bars
-- alongside a cursor:get in init.lua alongside whatever else gets
-- bolted on later.
--
-- Contract: every getter returns a typed value (string / number / bool
-- / list), or the supplied default when the option is missing or the
-- UCI lib itself is unavailable. None of them throw — UCI parse
-- failures swallowed so a transient /etc/config issue can't crash a
-- daemon mid-poll.

local M = {}

local function _cursor()
    local ok, uci = pcall(require, "uci")
    if not ok then
        ok, uci = pcall(require, "luci.model.uci")
    end
    if not ok then return nil end
    local cur_ok, cur = pcall(uci.cursor)
    if not cur_ok then return nil end
    return cur
end

-- Return the raw value for (config, section, option), trying the named
-- section first and falling back to the first unnamed section of that
-- type so a hand-edited /etc/config still works.
function M.get(config, section, option)
    local c = _cursor()
    if not c then return nil end

    local ok, v = pcall(c.get, c, config, section, option)
    if ok and v ~= nil then return v end

    local out
    pcall(function()
        c:foreach(config, section, function(s)
            if out == nil then out = s[option] end
        end)
    end)
    return out
end

function M.get_string(config, section, option, default)
    local v = M.get(config, section, option)
    if type(v) == "string" then return v end
    return default
end

function M.get_number(config, section, option, default)
    local v = M.get(config, section, option)
    if type(v) == "string" then
        local n = tonumber(v)
        if n then return n end
    elseif type(v) == "number" then
        return v
    end
    return default
end

function M.get_bool(config, section, option, default)
    local v = M.get(config, section, option)
    if v == "1" or v == true or v == "true" or v == "yes" or v == "on" then
        return true
    end
    if v == "0" or v == false or v == "false" or v == "no" or v == "off" then
        return false
    end
    return default
end

-- UCI list options come back as a Lua array of strings; UCI option-style
-- entries with a single value come back as a string. Normalise both to
-- a table of strings, or nil if absent.
function M.get_list(config, section, option)
    local v = M.get(config, section, option)
    if type(v) == "table" then return v end
    if type(v) == "string" and v ~= "" then return { v } end
    return nil
end

return M
