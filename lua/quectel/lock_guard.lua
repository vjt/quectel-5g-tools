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

return M
