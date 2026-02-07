-- Modem communication via serial port
-- Uses luaposix for serial I/O

local posix = require("posix")
local parser = require("quectel.parser")
local utils = require("quectel.utils")

local M = {}
M.__index = M

-- Default configuration
local DEFAULT_DEVICE = "/dev/ttyUSB2"
local DEFAULT_TIMEOUT = 2  -- seconds
local LOCK_FILE = "/var/lock/quectel-modem.lock"
local COMMAND_DELAY = 0.1  -- seconds between commands to reduce USB stress

--- Acquire exclusive lock on modem using lockfile
-- @return true on success, nil + error on failure
local function acquire_lock()
    -- Create lock directory if it doesn't exist
    posix.mkdir("/var/lock")  -- ignore error if exists

    -- Use O_EXCL for atomic lock file creation
    local fd = posix.open(LOCK_FILE, posix.O_CREAT + posix.O_EXCL + posix.O_WRONLY, 420)
    if not fd then
        -- Lock file exists - check if owner process still alive
        local rf = posix.open(LOCK_FILE, posix.O_RDONLY)
        if rf then
            local pid_str = posix.read(rf, 32)
            posix.close(rf)
            local pid = tonumber(pid_str)
            if pid then
                -- Check if process exists (kill with signal 0)
                local exists = posix.kill(pid, 0)
                if not exists then
                    -- Process is dead, remove stale lock
                    os.remove(LOCK_FILE)
                    fd = posix.open(LOCK_FILE, posix.O_CREAT + posix.O_EXCL + posix.O_WRONLY, 420)
                end
            else
                -- Invalid PID in lock file, remove it
                os.remove(LOCK_FILE)
                fd = posix.open(LOCK_FILE, posix.O_CREAT + posix.O_EXCL + posix.O_WRONLY, 420)
            end
        end
        if not fd then
            return nil, "Modem is locked by another process"
        end
    end

    -- Write our PID to the lock file
    posix.write(fd, tostring(posix.getpid()))
    posix.close(fd)
    return true
end

--- Release lock
local function release_lock()
    os.remove(LOCK_FILE)
end

--- Create a new modem instance
-- @param device Serial device path (default: /dev/ttyUSB2)
-- @param timeout Read timeout in seconds (default: 2)
-- @return Modem instance
function M.new(device, timeout)
    local self = setmetatable({}, M)
    self.device = device or DEFAULT_DEVICE
    self.timeout = timeout or DEFAULT_TIMEOUT
    self.fd = nil
    self.has_lock = false
    return self
end

--- Open the serial port
-- @return true on success, nil + error on failure
function M:open()
    -- Acquire lock first
    local ok, lock_err = acquire_lock()
    if not ok then
        return nil, lock_err
    end
    self.has_lock = true

    local fd, err = posix.open(self.device, posix.O_RDWR + posix.O_NOCTTY + posix.O_NONBLOCK)
    if not fd then
        release_lock()
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
        release_lock()
        self.has_lock = false
    end
end

--- Send AT command and read response
-- @param command AT command (without trailing \r\n)
-- @return Response string, or nil + error
function M:send(command)
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
    local start_time = os.time()
    local last_read_time = os.time()

    while true do
        -- Check overall timeout
        if os.time() - start_time > self.timeout then
            break
        end

        local data = posix.read(self.fd, 1024)
        if data and #data > 0 then
            table.insert(response, data)
            last_read_time = os.time()

            -- Check for end of response
            local full = table.concat(response)
            if full:match("\r\nOK\r\n$") or full:match("\r\nERROR\r\n$") then
                break
            end
        else
            -- No data available, small delay before retry
            -- But if we've been waiting too long since last data, give up
            if os.time() - last_read_time > 1 then
                break
            end
            utils.sleep(0.05)
        end
    end

    return table.concat(response)
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
-- @param bands Table of band numbers, or nil to reset to all
-- @return true on success
function M:set_bands(setting, bands)
    local value
    if bands and #bands > 0 then
        value = table.concat(bands, ":")
    else
        -- Empty means all bands
        value = ""
    end

    local resp, err = self:send('AT+QNWPREFCFG="' .. setting .. '",' .. value)
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

--- Backfill carrier aggregation entries with serving cell data
-- QCAINFO reports rssnr which is NOT the same as SINR from QENG="servingcell"
-- We backfill authoritative signal data from serving cell when available
-- @param status Status table with serving and ca fields
local function backfill_from_serving(status)
    if not status.serving then return end
    if not status.ca then return end

    local lte = status.serving.lte
    local nr = status.serving.nr5g

    -- Helper to backfill a single carrier from a serving cell source
    local function backfill_carrier(carrier, source)
        if not source then return end
        if not utils.same_cell(carrier, source) then return end

        -- Backfill signal values if missing
        if not carrier.rsrp and source.rsrp then carrier.rsrp = source.rsrp end
        if not carrier.rsrq and source.rsrq then carrier.rsrq = source.rsrq end
        if not carrier.sinr and source.sinr then carrier.sinr = source.sinr end

        -- Backfill bandwidth if available
        if not carrier.bandwidth_mhz and source.bandwidth_mhz then
            carrier.bandwidth_mhz = source.bandwidth_mhz
        end
    end

    -- Process PCC and all SCCs against appropriate serving cell
    local function process_carrier(carrier)
        if carrier.rat == "5g" then
            backfill_carrier(carrier, nr)
        else
            backfill_carrier(carrier, lte)
        end
    end

    if status.ca.pcc then
        process_carrier(status.ca.pcc)
    end

    for _, scc in ipairs(status.ca.scc or {}) do
        process_carrier(scc)
    end
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
    backfill_from_serving(status)

    return status
end

--- Get lightweight signal status (only serving cell + CA)
-- Use this for frequent polling (e.g., Prometheus) to reduce modem load
-- Only 2 AT commands instead of 6
-- @return Table with serving, ca (no device, operator, imei, neighbours)
function M:get_signal_status()
    local status = {}

    status.serving = self:get_serving_cell()
    status.ca = self:get_ca_info()

    utils.add_frequency_info(status)
    backfill_from_serving(status)

    return status
end

return M
