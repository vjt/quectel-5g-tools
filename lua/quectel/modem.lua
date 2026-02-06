-- Modem communication via serial port
-- Uses luaposix for serial I/O

local posix = require("posix")
local parser = require("quectel.parser")
local frequency = require("quectel.frequency")

local M = {}
M.__index = M

-- Default configuration
local DEFAULT_DEVICE = "/dev/ttyUSB2"
local DEFAULT_TIMEOUT = 2  -- seconds

--- Create a new modem instance
-- @param device Serial device path (default: /dev/ttyUSB2)
-- @param timeout Read timeout in seconds (default: 2)
-- @return Modem instance
function M.new(device, timeout)
    local self = setmetatable({}, M)
    self.device = device or DEFAULT_DEVICE
    self.timeout = timeout or DEFAULT_TIMEOUT
    self.fd = nil
    return self
end

--- Open the serial port
-- @return true on success, nil + error on failure
function M:open()
    local fd, err = posix.open(self.device, posix.O_RDWR + posix.O_NOCTTY + posix.O_NONBLOCK)
    if not fd then
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

    -- Small delay to let modem process command
    os.execute("sleep 0.1")

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
            os.execute("sleep 0.05")
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

    -- Enrich with frequency info
    if status.serving and status.serving.lte then
        local lte = status.serving.lte
        if lte.earfcn then
            lte.frequency_mhz = frequency.earfcn_to_mhz(lte.earfcn)
        end
        if lte.bandwidth_dl then
            lte.bandwidth_dl_mhz = frequency.lte_bandwidth_mhz(lte.bandwidth_dl)
        end
        if lte.bandwidth_ul then
            lte.bandwidth_ul_mhz = frequency.lte_bandwidth_mhz(lte.bandwidth_ul)
        end
    end

    if status.serving and status.serving.nr5g then
        local nr = status.serving.nr5g
        if nr.arfcn then
            nr.frequency_mhz = frequency.nrarfcn_to_mhz(nr.arfcn)
        end
        if nr.bandwidth then
            nr.bandwidth_mhz = frequency.nr5g_bandwidth_mhz(nr.bandwidth)
        end
    end

    -- Enrich CA info
    if status.ca then
        if status.ca.pcc then
            local pcc = status.ca.pcc
            if pcc.earfcn then
                if pcc.rat == "nr" then
                    pcc.frequency_mhz = frequency.nrarfcn_to_mhz(pcc.earfcn)
                else
                    pcc.frequency_mhz = frequency.earfcn_to_mhz(pcc.earfcn)
                end
            end
            if pcc.bandwidth_rb then
                pcc.bandwidth_mhz = frequency.lte_bandwidth_mhz(pcc.bandwidth_rb, true)
            end
        end
        for _, scc in ipairs(status.ca.scc) do
            if scc.earfcn then
                if scc.rat == "nr" then
                    scc.frequency_mhz = frequency.nrarfcn_to_mhz(scc.earfcn)
                else
                    scc.frequency_mhz = frequency.earfcn_to_mhz(scc.earfcn)
                end
            end
            if scc.bandwidth_rb then
                scc.bandwidth_mhz = frequency.lte_bandwidth_mhz(scc.bandwidth_rb, true)
            end
        end
    end

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

    -- Enrich with frequency info
    if status.serving and status.serving.lte then
        local lte = status.serving.lte
        if lte.earfcn then
            lte.frequency_mhz = frequency.earfcn_to_mhz(lte.earfcn)
        end
        if lte.bandwidth_dl then
            lte.bandwidth_dl_mhz = frequency.lte_bandwidth_mhz(lte.bandwidth_dl)
        end
        if lte.bandwidth_ul then
            lte.bandwidth_ul_mhz = frequency.lte_bandwidth_mhz(lte.bandwidth_ul)
        end
    end

    if status.serving and status.serving.nr5g then
        local nr = status.serving.nr5g
        if nr.arfcn then
            nr.frequency_mhz = frequency.nrarfcn_to_mhz(nr.arfcn)
        end
        if nr.bandwidth then
            nr.bandwidth_mhz = frequency.nr5g_bandwidth_mhz(nr.bandwidth)
        end
    end

    -- Enrich CA info
    if status.ca then
        if status.ca.pcc then
            local pcc = status.ca.pcc
            if pcc.earfcn then
                if pcc.rat == "nr" then
                    pcc.frequency_mhz = frequency.nrarfcn_to_mhz(pcc.earfcn)
                else
                    pcc.frequency_mhz = frequency.earfcn_to_mhz(pcc.earfcn)
                end
            end
            if pcc.bandwidth_rb then
                pcc.bandwidth_mhz = frequency.lte_bandwidth_mhz(pcc.bandwidth_rb, true)
            end
        end
        for _, scc in ipairs(status.ca.scc or {}) do
            if scc.earfcn then
                if scc.rat == "nr" then
                    scc.frequency_mhz = frequency.nrarfcn_to_mhz(scc.earfcn)
                else
                    scc.frequency_mhz = frequency.earfcn_to_mhz(scc.earfcn)
                end
            end
            if scc.bandwidth_rb then
                scc.bandwidth_mhz = frequency.lte_bandwidth_mhz(scc.bandwidth_rb, true)
            end
        end
    end

    return status
end

return M
