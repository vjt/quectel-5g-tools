-- Prometheus collector for the 5g-watchdog daemon.
-- Install to /usr/lib/lua/prometheus-collectors/quectel-watchdog.lua
--
-- Reads the key=value state file written atomically each tick by
-- /usr/bin/5g-watchdog. The collector is intentionally trivial: all
-- the logic lives in the daemon. If the file is missing (daemon not
-- running, or hasn't ticked yet) the scrape is a no-op so prom-node
-- doesn't blow up — the absence of `quectel_watchdog_*` series is
-- itself a useful alert signal.

local STATE_PATH = "/var/run/5g-watchdog.state"

local function read_state()
    local f = io.open(STATE_PATH, "r")
    if not f then return nil end
    local t = {}
    for line in f:lines() do
        local k, v = line:match("^(%S+)=(.*)$")
        if k then t[k] = v end
    end
    f:close()
    return t
end

local function scrape()
    if not metric then
        error("No metric function available - check prometheus-node-exporter-lua installation")
    end

    local s = read_state()
    if not s then return end

    local function num(key) return tonumber(s[key]) or 0 end

    local nr_attached       = metric("quectel_watchdog_nr_attached", "gauge")
    local nr_capable        = metric("quectel_watchdog_nr_capable", "gauge")
    local connected         = metric("quectel_watchdog_connected", "gauge")
    local consecutive       = metric("quectel_watchdog_consecutive_degraded_samples", "gauge")
    local cooldown_until    = metric("quectel_watchdog_cooldown_until_timestamp_seconds", "gauge")
    local last_action       = metric("quectel_watchdog_last_action_timestamp_seconds", "gauge")
    local last_recovery     = metric("quectel_watchdog_last_recovery_duration_seconds", "gauge")
    local actions24h        = metric("quectel_watchdog_actions_24h", "gauge")
    local actions_total     = metric("quectel_watchdog_actions_total", "counter")
    local consecutive_failed = metric("quectel_watchdog_consecutive_failed_actions", "gauge")
    local capped            = metric("quectel_watchdog_capped", "gauge")
    local updated           = metric("quectel_watchdog_updated_timestamp_seconds", "gauge")

    nr_attached({}, num("nr_attached"))
    nr_capable({}, num("nr_capable"))
    connected({}, num("connected"))
    consecutive({}, num("consecutive_degraded"))
    cooldown_until({}, num("cooldown_until"))
    last_action({}, num("last_action_ts"))
    last_recovery({}, num("last_recovery_seconds"))
    actions24h({}, num("actions_24h"))
    actions_total({ stage = "disable_enable" }, num("actions_total_disable_enable"))
    actions_total({ stage = "mode_toggle" }, num("actions_total_mode_toggle"))
    consecutive_failed({}, num("consecutive_failed_actions"))
    capped({}, num("capped"))
    updated({}, num("updated_ts"))
end

return { scrape = scrape }
