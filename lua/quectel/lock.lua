--- Exclusive lock for the modem's AT port.
--
-- Every quectel-5g-tools consumer (5g-watchdog, 5g-led-bars, 5g-monitor,
-- the prometheus collectors, ad-hoc quectel-at calls) shares one serial
-- port, so they take turns through this lockfile.
--
-- The design is shaped by the 2026-08-13 → 2026-09-01 outage, in which
-- 5g-watchdog logged "Modem is locked by another process" on every probe
-- for twenty days. It published zeroes throughout, so the dashboard
-- reported "NR detached" while the modem was in fact attached. Only the
-- reboot for the r7 flash cleared it — /var/lock is tmpfs.
--
-- Three properties keep that from recurring:
--
--   1. The lockfile is published atomically, via link(2) from a fully
--      written temporary file. It is never observable without an owner.
--      (The previous version created it empty with O_CREAT|O_EXCL and
--      wrote the PID afterwards.)
--   2. Release only removes a lockfile this process owns. (The previous
--      version removed whichever lockfile was present, so one consumer
--      could free another's lock and both would then drive the port.)
--   3. A holder may not keep the lock beyond max_hold_seconds. Past that
--      ceiling any waiter reclaims it.
--
-- Property 3 is the one that ends the outage. Staleness cannot be
-- decided by kill(pid, 0) alone: a holder hung on an unresponsive port
-- looks alive, and so does an unrelated process that has since been
-- given the dead holder's recycled PID. Both were consistent with the
-- evidence and neither is distinguishable after the fact, so the lock
-- does not try — it bounds how long *any* holder can block the port. The
-- ceiling sits well above the slowest legitimate hold (two AT commands
-- at the 2s timeout, ~4s) and far below the poll intervals that matter.
--
-- Times come from utils.now() — CLOCK_MONOTONIC, system-wide and
-- therefore comparable between processes, and unaffected by the NTP step
-- this router takes at every boot for want of an RTC.

local posix = require("posix")
local utils = require("quectel.utils")

local M = {}

M.DEFAULT_PATH = "/var/lock/quectel-modem.lock"
M.DEFAULT_WAIT_MS = 2000
M.POLL_MS = 50

--- Longest a holder may keep the lock before waiters may reclaim it.
M.DEFAULT_MAX_HOLD_SECONDS = 15

-- Seams for the tests: overridden to drive the clock, identity and
-- liveness checks without spawning real processes.
M.now = utils.now

-- luaposix disagrees with itself across releases: getpid() answers with a
-- bare number on the router's build and with a table of process ids on
-- newer ones. Normalise, or the lockfile gets a table written into it.
M.getpid = function()
    local p = posix.getpid()
    if type(p) == "table" then return p.pid end
    return p
end

M.is_alive = function(pid) return posix.kill(pid, 0) ~= nil end

--- Directory component of a path, or "." when there is none.
local function dirname(path)
    return path:match("^(.*)/[^/]*$") or "."
end

--- Read the current owner.
-- @param path lockfile path
-- @return table {pid, acquired_at}, or nil if absent or unparseable
function M.read(path)
    local f = io.open(path or M.DEFAULT_PATH, "r")
    if not f then return nil end
    local contents = f:read("*a") or ""
    f:close()

    local pid, acquired_at = contents:match("^(%d+)%s+([%d%.]+)")
    if not pid then return nil end
    return { pid = tonumber(pid), acquired_at = tonumber(acquired_at) }
end

--- Publish a lockfile atomically, or fail if one already exists.
-- Writes the owner to a private temporary file and link(2)s it into
-- place: the link either succeeds outright or the lockfile was already
-- there, and it is complete the moment it becomes visible.
-- @return true if we now hold the lock
local function try_create(path, pid, acquired_at)
    local tmp = string.format("%s.tmp.%d", path, pid)
    local f = io.open(tmp, "w")
    if not f then return false end
    f:write(string.format("%d %.3f\n", pid, acquired_at))
    f:close()

    local linked = posix.link(tmp, path)
    os.remove(tmp)
    return linked ~= nil
end

--- Acquire the modem lock.
-- Polls until the lock is free, reclaimable, or the wait elapses, so
-- consumers racing on the same port queue instead of failing outright.
-- @param opts table: path, wait_ms, max_hold_seconds (all optional)
-- @return true on success, or nil + error message
function M.acquire(opts)
    opts = opts or {}
    local path = opts.path or M.DEFAULT_PATH
    local wait_ms = opts.wait_ms or M.DEFAULT_WAIT_MS
    local max_hold = opts.max_hold_seconds or M.DEFAULT_MAX_HOLD_SECONDS

    posix.mkdir(dirname(path))  -- ignored if it already exists

    local attempts = math.max(1, math.floor(wait_ms / M.POLL_MS))
    local pid = M.getpid()

    for attempt = 1, attempts do
        if try_create(path, pid, M.now()) then
            return true
        end

        -- Someone holds it. Decide whether that claim still stands.
        local owner = M.read(path)
        local reclaim
        if not owner then
            -- Corrupt or truncated: no owner can be established, and
            -- leaving it in place would block the port indefinitely.
            reclaim = true
        elseif owner.pid == pid then
            -- Our own lock, left behind by an earlier operation in this
            -- process that did not release. Reclaiming it keeps a leak
            -- from deadlocking us against ourselves.
            reclaim = true
        elseif not M.is_alive(owner.pid) then
            reclaim = true
        elseif (M.now() - (owner.acquired_at or 0)) > max_hold then
            reclaim = true
        end

        if reclaim then
            os.remove(path)
            if try_create(path, pid, M.now()) then
                return true
            end
            -- Lost the race to another waiter that reclaimed first; fall
            -- through and retry on the next pass.
        end

        if attempt < attempts then
            utils.sleep(M.POLL_MS / 1000)
        end
    end

    return nil, string.format(
        "Modem is locked by another process (waited %d ms)", wait_ms)
end

--- Release the modem lock, if this process owns it.
-- @param opts table: path (optional)
-- @return true on success, or nil + error message
function M.release(opts)
    opts = opts or {}
    local path = opts.path or M.DEFAULT_PATH

    local owner = M.read(path)
    if not owner then
        -- Already gone: nothing held, nothing to answer for.
        return true
    end
    if owner.pid ~= M.getpid() then
        return nil, string.format(
            "refusing to release lock: owner is pid %d", owner.pid)
    end

    os.remove(path)
    return true
end

return M
