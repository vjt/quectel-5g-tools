--- Safety net for a cell lock that is applied automatically at boot.
--
-- An LTE cell lock pins the modem to a whitelist of cells. That is the
-- only thing that reliably keeps this device on an EN-DC-capable anchor
-- (see the 2026-09-04 entry in nr-availability-journal.md), but it
-- carries a failure mode with teeth: if every locked cell becomes
-- unreachable, the modem has nowhere to reselect to and there is no
-- service at all. Not degraded — none.
--
-- That happened. A lock onto a single cell held for 21 minutes, the
-- cell went away, and the WAN was down for ~14 minutes; the AT port was
-- mute by then, so the lock could not even be cleared by hand. What
-- saved it was that cell locks do not survive a reboot.
--
-- Re-applying the lock at boot — which is the point of this module's
-- caller — takes that away. A lock that comes back every boot is a lock
-- a reboot cannot clear. So the escape hatch has to be replaced, and
-- replaced with something better than "be physically present and know
-- to reboot": after applying, watch for service, and if it does not
-- appear within the window, drop the lock and let the modem roam free.
-- Unattended, and faster than a person would manage.
--
-- The rule is deliberately one-sided. It asks only "did this lock
-- strand us", never "is the link healthy" — that is the watchdog's job.
-- Service observed even once means the lock did not strand us, and the
-- guard stays out of the way for the rest of the boot.

local M = {}

--- Is there service on the bearer interface?
-- @param ifstatus decoded `ifstatus <iface>` output, or nil if it could
--   not be read
-- @return true only when the interface is demonstrably up
function M.service_ok(ifstatus)
    -- nil means we could not tell. That is not evidence the lock broke
    -- anything, and rolling back on a failed shell-out would drop
    -- perfectly good locks.
    if type(ifstatus) ~= "table" then return false end
    return ifstatus.up == true
end

--- Should the cell lock be rolled back?
-- @param s table:
--   elapsed        seconds since the lock was applied
--   verify_seconds how long to wait for service (0 disables the guard)
--   service_seen   whether service has been observed at any point since
-- @return true when the lock should be cleared
function M.should_rollback(s)
    if not s.verify_seconds or s.verify_seconds <= 0 then
        -- Verification switched off: keep the lock whatever happens.
        return false
    end
    if s.service_seen then
        -- The lock did not strand us. Anything that goes wrong later is
        -- a different problem with a different owner.
        return false
    end
    return (s.elapsed or 0) >= s.verify_seconds
end

--- Is this a cell the modem can actually be locked to?
--
-- Locking to PCI 999 on 2026-09-04 did not fail loudly: the modem took
-- the command, stored something that read back as "EARFCN 0 PCI 0",
-- stranded the radio with nothing to camp on, and then refused
-- `AT+QNWLOCK="common/4g",0` with +CME ERROR 904 — so the rollback
-- could not undo it either and only a reboot cleared it. Range-check
-- before the value reaches the modem; an obviously wrong entry should
-- be a config error, not an outage.
--
-- LTE PCI is 0..503 (168 groups x 3). EARFCN is 0..262143, though real
-- deployments sit far below that.
-- @return true when the cell is usable, false otherwise
function M.valid_cell(c)
    if type(c) ~= "table" then return false end
    local e, p = c.earfcn, c.pci
    if type(e) ~= "number" or type(p) ~= "number" then return false end
    if e < 0 or e > 262143 then return false end
    if p < 0 or p > 503 then return false end
    return true
end

--- Validate a whole cell list.
-- @return true, or false plus the first offending entry
function M.validate_cells(cells)
    for _, c in ipairs(cells or {}) do
        if not M.valid_cell(c) then return false, c end
    end
    return true
end

--- Should the boot-time apply be skipped?
--
-- The rollback cannot always undo a bad lock: if the radio is far
-- enough gone the clear command is rejected outright, and only a reboot
-- drops the lock. Re-applying the same list on the next boot would then
-- be a loop — apply, strand, reboot, apply. So a failed lock records
-- the list that failed, and that exact list is not tried again.
--
-- Editing the list counts as new intent and clears the block, which
-- also gives the operator an obvious way out: change the config.
-- @param marker contents of the failure marker, or nil when absent
-- @param current the currently configured cell list, same format
-- @return true when the apply should be skipped
function M.should_skip_boot_apply(marker, current)
    if type(marker) ~= "string" then return false end
    local function norm(x)
        return (tostring(x or ""):gsub("%s+", " "):gsub("^ ", ""):gsub(" $", ""))
    end
    local m = norm(marker)
    if m == "" then return false end
    return m == norm(current)
end

return M
