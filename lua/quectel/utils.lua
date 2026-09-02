-- Utility functions for Quectel modem library

local M = {}

-- Load frequency module for enrichment
local frequency = require("quectel.frequency")

-- Load posix.time for sleep (optional, graceful fallback)
local posix_time_ok, posix_time = pcall(require, "posix.time")

--- Get current time with monotonic clock if available
-- Returns seconds as float with nanosecond precision when possible
-- Falls back to os.time() if posix.time unavailable
-- @return Current time in seconds
function M.now()
    if posix_time_ok and posix_time.clock_gettime then
        local ts = posix_time.clock_gettime(posix_time.CLOCK_MONOTONIC)
        return ts.tv_sec + ts.tv_nsec / 1e9
    else
        return os.time()
    end
end

-- A wall-clock jump smaller than this is ordinary NTP slew and is
-- ignored; anything larger is treated as a step. Has to sit above the
-- jitter of a normal poll cycle and well below the smallest interval we
-- make decisions on.
M.CLOCK_STEP_MIN = 10

--- Detect a wall-clock step by comparing it against the monotonic clock.
-- @param prev_wall os.time() at the previous sample
-- @param prev_mono M.now() at the previous sample
-- @param wall os.time() now
-- @param mono M.now() now
-- @return seconds the wall clock jumped (signed), or 0 if it only slewed
--
-- Both clocks advance together in normal operation, so any difference
-- between how much each moved is the step. Hosts without an RTC — jeeves
-- included — boot with a stale clock and get stepped by sysntpd once the
-- network is up, which silently inflates every duration derived from
-- os.time(). Callers use the returned delta to shift their stored
-- wall-clock bases so durations stay true *and* the timestamps they
-- publish still name the corrected instant.
function M.clock_step(prev_wall, prev_mono, wall, mono)
    if not prev_wall or not prev_mono then return 0 end
    local drift = (wall - prev_wall) - (mono - prev_mono)
    if math.abs(drift) < M.CLOCK_STEP_MIN then return 0 end
    -- Round toward zero-ish: os.time() is whole seconds, M.now() is
    -- fractional, so a sub-second remainder here is measurement noise.
    return drift >= 0 and math.floor(drift + 0.5) or -math.floor(-drift + 0.5)
end

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
-- @param a First cell
-- @param b Second cell
-- @return true if the two describe the same carrier
--
-- ARFCN is the discriminator whenever both sides have one: it names the
-- carrier frequency, so two entries on different ARFCNs are different
-- carriers regardless of what else matches. PCI alone is only enough
-- when one side doesn't report an ARFCN.
--
-- This matters for NR carrier aggregation, where the carriers of a
-- single gNB commonly share a PCI. A real SA sample from
-- vjt/openwrt-glinet-x3000#1 has band 25 (arfcn 396250) and band 71
-- (arfcn 125530) both on PCI 484 — under a plain "pci or arfcn" match
-- the band-71 SCC would inherit the band-25 serving cell's RSRP and we
-- would publish a measurement that was never taken.
function M.same_cell(a, b)
    if not a or not b then return false end

    if a.arfcn and b.arfcn then
        return a.arfcn == b.arfcn
    end

    return (a.pci and b.pci and a.pci == b.pci) or false
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

--- Backfill carrier aggregation entries with serving cell data
-- QCAINFO reports rssnr, which is NOT the same as SINR from
-- QENG="servingcell", and in some shapes reports no signal fields at
-- all — notably the 5-field NR5G PCC line an SA-attached modem emits.
-- The serving-cell reply is authoritative for RSRP/RSRQ/SINR, so we
-- copy it onto whichever carriers match by PCI/ARFCN.
--
-- This is the sole path by which standalone-NR signal reaches
-- 5g-led-bars, 5g-watchdog and the prometheus collector: without it an
-- SA modem reports rsrp=nil and every consumer decides there is no
-- signal on a perfectly good link (vjt/openwrt-glinet-x3000#1).
-- @param status Status table with serving and ca fields
function M.backfill_from_serving(status)
    if not status.serving then return end
    if not status.ca then return end

    local lte = status.serving.lte
    local nr = status.serving.nr5g

    -- Helper to backfill a single carrier from a serving cell source
    local function backfill_carrier(carrier, source)
        if not source then return end
        if not M.same_cell(carrier, source) then return end

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

return M
