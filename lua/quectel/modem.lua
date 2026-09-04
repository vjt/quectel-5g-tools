-- Modem communication via serial port
-- Uses luaposix for serial I/O

local posix = require("posix")
local parser = require("quectel.parser")
local utils = require("quectel.utils")
local lock = require("quectel.lock")

local M = {}
M.__index = M

-- Default configuration
local DEFAULT_DEVICE = "/dev/ttyUSB2"
local DEFAULT_TIMEOUT = 2  -- seconds
local COMMAND_DELAY = 0.1  -- seconds between commands to reduce USB stress
-- Max wait when another quectel-5g-tools consumer holds the lock. A
-- typical AT round-trip (servingcell + qcainfo) takes well under 1 s,
-- so 2 s covers normal hand-off between 5g-led-bars (10 s tick),
-- the prometheus collector (per-scrape) and ad-hoc 5g-info / 5g-monitor
-- runs without any of them silently giving up. Tuned via
-- quectel.modem.lock_wait_ms in /etc/config/quectel if needed.
--
-- 5g-watchdog overrides this with a much longer wait: it polls once a
-- minute and must never be the consumer that loses the race, having
-- already spent twenty days locked out while publishing zeroes.
local LOCK_WAIT_MS_DEFAULT = 2000

-- ---------------------------------------------------------------------
-- shared read cache
-- ---------------------------------------------------------------------
--
-- Three daemons ask the modem the same questions on overlapping timers:
-- the prometheus collector (per telegraf scrape, ~10s), 5g-led-bars
-- (~60s) and 5g-watchdog (~60s), plus ad-hoc 5g-info / 5g-monitor runs.
-- Each one took the lock and ran the same AT round-trip, so their timers
-- periodically collided and whoever lost the race logged
-- "Modem is locked by another process" — misleading, since nothing was
-- actually wrong with the modem.
--
-- A few seconds of sharing removes the collision entirely: the first
-- caller in a window pays the AT round-trip, everyone else reads the
-- file and never touches the lock. Cell metrics don't move meaningfully
-- inside one TTL, and the modem is doing the same measurement averaging
-- internally regardless of how often we ask.
local CACHE_DIR = "/var/run/quectel-at-cache"
local CACHE_TTL_DEFAULT = 5

-- Only read-only queries are shareable. Anything that sets state must
-- always reach the modem, and must never be served from — or written
-- to — the cache.
local CACHEABLE = {
    ["ATI"] = true,
    ["AT+GSN"] = true,
    ["AT+QSPN"] = true,
    ["AT+QCAINFO"] = true,
    ["AT+QNWINFO"] = true,
    ['AT+QENG="servingcell"'] = true,
    ['AT+QENG="neighbourcell"'] = true,
}

local function is_cacheable(cmd)
    if CACHEABLE[cmd] then return true end
    -- Query forms take a single quoted argument and nothing else; the
    -- presence of a comma means a value follows, i.e. it's a write.
    if cmd:match('^AT%+QNWPREFCFG="[%w_/]+"$') then return true end
    if cmd:match('^AT%+QNWLOCK="[%w_/]+"$') then return true end
    return false
end

local function cache_path(cmd)
    return CACHE_DIR .. "/" .. cmd:gsub("[^%w]", "_")
end

-- Entries are "<unix-ts>\n<raw response>". Stamping the timestamp inside
-- the file rather than leaning on mtime keeps this to plain io, and the
-- 1s resolution of os.time() is well below any useful TTL.
local function cache_get(cmd, ttl)
    local f = io.open(cache_path(cmd), "r")
    if not f then return nil end
    local ts = tonumber(f:read("*l") or "")
    local body = f:read("*a")
    f:close()
    if not ts or not body or body == "" then return nil end
    if os.time() - ts > ttl then return nil end
    return body
end

local function cache_put(cmd, response)
    posix.mkdir(CACHE_DIR)  -- ignore error if exists
    local path = cache_path(cmd)
    local tmp = path .. ".tmp"
    local f = io.open(tmp, "w")
    if not f then return end
    f:write(tostring(os.time()), "\n", response)
    f:close()
    os.rename(tmp, path)
end

-- Drop every cached reply. Called whenever we send something that isn't
-- a known read-only query, i.e. anything that may have changed the
-- modem's state. 5g-lock reads a lock back immediately after setting it
-- to confirm it took; without this it could be shown the pre-write
-- answer and report the wrong outcome.
local function cache_invalidate()
    if type(posix.dir) ~= "function" then return end
    local ok, names = pcall(posix.dir, CACHE_DIR)
    if not ok or type(names) ~= "table" then return end
    for _, name in ipairs(names) do
        if name ~= "." and name ~= ".." then
            os.remove(CACHE_DIR .. "/" .. name)
        end
    end
end

--- Create a new modem instance
-- @param device Serial device path (default: /dev/ttyUSB2)
-- @param timeout Read timeout in seconds (default: 2)
-- @param lock_wait_ms Optional max wait for /var/lock/quectel-modem.lock,
--   in milliseconds. Defaults to LOCK_WAIT_MS_DEFAULT (2000ms). Bump
--   this for callers that can tolerate a longer queue behind whichever
--   helper is currently holding the lock — e.g. 5g-watchdog at startup,
--   when 5g-led-bars / 5g-monitor may be mid-poll.
-- @param cache_ttl Optional seconds a read-only AT reply may be shared
--   with the other quectel-5g-tools consumers (default 5). Pass 0 to
--   force every query onto the wire — right for one-shot diagnostics
--   where a stale-by-seconds answer would mislead.
-- @param lock_max_hold_seconds Optional ceiling on how long *any* holder
--   may keep the port before a waiter reclaims it. See quectel.lock.
-- @return Modem instance
function M.new(device, timeout, lock_wait_ms, cache_ttl, lock_max_hold_seconds)
    local self = setmetatable({}, M)
    self.device = device or DEFAULT_DEVICE
    self.timeout = timeout or DEFAULT_TIMEOUT
    self.lock_wait_ms = lock_wait_ms or LOCK_WAIT_MS_DEFAULT
    self.cache_ttl = cache_ttl or CACHE_TTL_DEFAULT
    self.lock_max_hold_seconds = lock_max_hold_seconds
    self.fd = nil
    self.has_lock = false
    return self
end

--- Open the serial port
-- @return true on success, nil + error on failure
function M:open()
    -- Acquire lock first
    local ok, lock_err = lock.acquire({
        wait_ms = self.lock_wait_ms,
        max_hold_seconds = self.lock_max_hold_seconds,
    })
    if not ok then
        return nil, lock_err
    end
    self.has_lock = true

    local fd, err = posix.open(self.device, posix.O_RDWR + posix.O_NOCTTY + posix.O_NONBLOCK)
    if not fd then
        lock.release()
        self.has_lock = false
        return nil, "Failed to open " .. self.device .. ": " .. (err or "unknown error")
    end
    self.fd = fd

    -- Configure serial port for raw mode
    if posix.tcgetattr and posix.tcsetattr then
        local termios = posix.tcgetattr(fd)
        if termios then
            termios.iflag = 0
            termios.oflag = 0
            termios.lflag = 0
            -- CS8 | CREAD | CLOCAL (8N1, enable receiver, ignore modem control)
            termios.cflag = 0x8B0
            posix.tcsetattr(fd, posix.TCSANOW, termios)
        end
    end

    return true
end

--- Close the serial port
function M:close()
    if self.fd then
        posix.close(self.fd)
        self.fd = nil
    end
    if self.has_lock then
        lock.release()
        self.has_lock = false
    end
end

--- Send AT command and read response
-- @param command AT command (without trailing \r\n)
-- @return Response string, or nil + error
function M:send(command)
    -- Cache lookup happens before open() on purpose: a hit must not take
    -- the lock at all, otherwise the contention this cache exists to
    -- remove is still paid on every call.
    local cacheable = self.cache_ttl > 0 and is_cacheable(command)
    if cacheable then
        local hit = cache_get(command, self.cache_ttl)
        if hit then return hit end
    end

    if not self.fd then
        local ok, err = self:open()
        if not ok then return nil, err end
    end

    -- Send command
    local cmd = command .. "\r\n"
    local written = posix.write(self.fd, cmd)
    if not written or written ~= #cmd then
        return nil, "Failed to write command"
    end

    -- Small delay to let modem process command (using nanoutils.sleep, not os.execute)
    utils.sleep(COMMAND_DELAY)

    -- Read response with timeout using non-blocking reads
    local response = {}
    local start_time = utils.now()
    local last_read_time = utils.now()

    while true do
        -- Check overall timeout
        if utils.now() - start_time > self.timeout then
            break
        end

        local data = posix.read(self.fd, 1024)
        if data and #data > 0 then
            table.insert(response, data)
            last_read_time = utils.now()

            -- Check for end of response
            local full = table.concat(response)
            if full:match("\r\nOK\r\n$") or full:match("\r\nERROR\r\n$") then
                break
            end
        else
            -- No data available, small delay before retry
            -- But if we've been waiting too long since last data, give up
            if utils.now() - last_read_time > 1 then
                break
            end
            utils.sleep(0.05)
        end
    end

    local full = table.concat(response)

    -- An empty reply is a failure, not an empty result. The port opened,
    -- we wrote the command, and the modem said nothing at all — that
    -- means the AT server is mute (2026-08-12: the RM520N's USB AT
    -- endpoint died while MBIM kept working).
    --
    -- Returning "" here used to let the parsers hand back a well-formed
    -- table with every field nil, which callers then read as a genuine
    -- "no carriers, not connected" — so a mute modem was indistinguishable
    -- from a real outage all the way up the stack. Fail loudly instead.
    if full == "" then
        return nil, string.format("no response from %s (mute after %.1fs)",
            self.device, self.timeout)
    end

    if cacheable then
        cache_put(command, full)
    else
        -- Not a known read-only query, so assume it changed something
        -- and stop serving anyone the pre-change view.
        cache_invalidate()
    end

    return full
end

--- Get device info (ATI)
-- @return Table with manufacturer, model, revision
function M:get_device_info()
    local resp, err = self:send("ATI")
    if not resp then return nil, err end
    return parser.parse_ati(resp)
end

--- Get operator info (AT+QSPN)
-- @return Table with operator, mcc_mnc
function M:get_operator()
    local resp, err = self:send("AT+QSPN")
    if not resp then return nil, err end
    return parser.parse_qspn(resp)
end

--- Get serving cell info (AT+QENG="servingcell")
-- @return Table with state, lte, nr5g
function M:get_serving_cell()
    local resp, err = self:send('AT+QENG="servingcell"')
    if not resp then return nil, err end
    return parser.parse_serving_cell(resp)
end

--- Get carrier aggregation info (AT+QCAINFO)
-- @return Table with pcc, scc
function M:get_ca_info()
    local resp, err = self:send("AT+QCAINFO")
    if not resp then return nil, err end
    return parser.parse_qcainfo(resp)
end

--- Get neighbour cells (AT+QENG="neighbourcell")
-- @return List of neighbour cells
function M:get_neighbours()
    local resp, err = self:send('AT+QENG="neighbourcell"')
    if not resp then return nil, err end
    return parser.parse_neighbours(resp)
end

--- Get IMEI (AT+GSN)
-- @return IMEI string
function M:get_imei()
    local resp, err = self:send("AT+GSN")
    if not resp then return nil, err end
    for line in resp:gmatch("[^\r\n]+") do
        line = line:match("^%s*(.-)%s*$")
        if line:match("^%d+$") then
            return line
        end
    end
    return nil
end

--- Get current band configuration
-- @param setting "mode_pref", "lte_band", or "nsa_nr5g_band"
-- @return Setting value (string or table of bands)
function M:get_band_config(setting)
    local resp, err = self:send('AT+QNWPREFCFG="' .. setting .. '"')
    if not resp then return nil, err end
    local _, value = parser.parse_qnwprefcfg(resp)
    return value
end

--- Set band configuration
-- @param setting "lte_band" or "nsa_nr5g_band"
-- @param bands Table of band numbers, or empty/nil to reset to all supported bands
-- @return true on success
function M:set_bands(setting, bands)
    if bands and #bands > 0 then
        local value = table.concat(bands, ":")
        local resp, err = self:send('AT+QNWPREFCFG="' .. setting .. '",' .. value)
        if not resp then return nil, err end
        return resp:match("OK") ~= nil
    end

    -- Reset to all bands: query carrier policy for the full supported set
    local resp, err = self:send('AT+QNWPREFCFG="policy_band"')
    if not resp then return nil, err end
    local _, all_bands = parser.parse_qnwprefcfg_from(resp, setting)
    if not all_bands or #all_bands == 0 then
        return nil, "could not determine supported bands from policy_band"
    end
    local value = table.concat(all_bands, ":")
    resp, err = self:send('AT+QNWPREFCFG="' .. setting .. '",' .. value)
    if not resp then return nil, err end
    return resp:match("OK") ~= nil
end

--- Get cell lock status
-- @param lock_type "common/4g" or "common/5g"
-- @return Parsed lock info table, or nil + error
function M:get_cell_lock(lock_type)
    local resp, err = self:send('AT+QNWLOCK="' .. lock_type .. '"')
    if not resp then return nil, err end
    return parser.parse_qnwlock(resp)
end

--- Set 4G cell lock
-- @param cells Table of {earfcn=N, pci=N} pairs, or empty table to clear
-- @return true on success, nil + error on failure
function M:set_cell_lock_4g(cells)
    local cmd
    if not cells or #cells == 0 then
        cmd = 'AT+QNWLOCK="common/4g",0'
    else
        local parts = { string.format('AT+QNWLOCK="common/4g",%d', #cells) }
        for _, cell in ipairs(cells) do
            table.insert(parts, string.format(",%d,%d", cell.earfcn, cell.pci))
        end
        cmd = table.concat(parts)
    end

    local resp, err = self:send(cmd)
    if not resp then return nil, err end
    return resp:match("OK") ~= nil
end

--- Set 5G NR cell lock
-- @param cells Table of {pci=N, arfcn=N, scs=N, band=N}, or empty table to clear
-- @return true on success, nil + error on failure
function M:set_cell_lock_5g(cells)
    local cmd
    if not cells or #cells == 0 then
        cmd = 'AT+QNWLOCK="common/5g",0'
    else
        -- 5G lock supports one cell at a time
        local cell = cells[1]
        cmd = string.format('AT+QNWLOCK="common/5g",%d,%d,%d,%d',
            cell.pci, cell.arfcn, cell.scs, cell.band)
    end

    local resp, err = self:send(cmd)
    if not resp then return nil, err end
    return resp:match("OK") ~= nil
end

--- Clear cell lock
-- @param lock_type "common/4g" or "common/5g"
-- @return true on success, nil + error on failure
function M:clear_cell_lock(lock_type)
    local resp, err = self:send('AT+QNWLOCK="' .. lock_type .. '",0')
    if not resp then return nil, err end
    return resp:match("OK") ~= nil
end

--- Get complete modem status
-- Returns all information needed for monitoring/exporting
-- @return Table with device, operator, serving, ca, neighbours
function M:get_status()
    local status = {}

    status.device = self:get_device_info()
    status.operator = self:get_operator()
    status.imei = self:get_imei()
    status.serving = self:get_serving_cell()
    status.ca = self:get_ca_info()
    status.neighbours = self:get_neighbours()

    utils.add_frequency_info(status)
    utils.backfill_from_serving(status)

    return status
end

--- Get lightweight signal status (only serving cell + CA)
-- Use this for frequent polling (e.g., Prometheus) to reduce modem load
-- Only 2 AT commands instead of 6
-- @return Table with serving, ca (no device, operator, imei, neighbours)
-- Both reads must succeed. Previously the errors were dropped on the
-- floor and a status table with serving=nil, ca=nil was returned, which
-- every caller reads as a valid "no carriers, not connected" sample —
-- so an unreachable modem was reported as a genuine outage rather than
-- as a failure to measure. Surface the error instead and let callers
-- decide.
function M:get_signal_status()
    local serving, serr = self:get_serving_cell()
    if not serving then return nil, serr end

    local ca, cerr = self:get_ca_info()
    if not ca then return nil, cerr end

    local status = { serving = serving, ca = ca }

    utils.add_frequency_info(status)
    utils.backfill_from_serving(status)

    return status
end

return M
