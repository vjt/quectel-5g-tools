-- Prometheus collector for the 5g-watchdog daemon.
-- Install to /usr/lib/lua/prometheus-collectors/quectel-watchdog.lua
--
-- Reads the key=value state file written atomically each tick by
-- /usr/bin/5g-watchdog. The collector is intentionally trivial: all
-- the logic lives in the daemon. If the file is missing (daemon not
-- running, or hasn't ticked yet) the scrape is a no-op so prom-node
-- doesn't blow up — the absence of `quectel_watchdog_*` series is
-- itself a useful alert signal.

-- luacheck: globals metric

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
    local nr_carriers       = metric("quectel_watchdog_nr_carriers", "gauge")
    local lte_carriers      = metric("quectel_watchdog_lte_carriers", "gauge")
    local nr_capable        = metric("quectel_watchdog_nr_capable", "gauge")
    local connected         = metric("quectel_watchdog_connected", "gauge")
    local consecutive       = metric("quectel_watchdog_consecutive_degraded_samples", "gauge")
    local cooldown_until    = metric("quectel_watchdog_cooldown_until_timestamp_seconds", "gauge")
    local last_action       = metric("quectel_watchdog_last_action_timestamp_seconds", "gauge")
    local last_recovery     = metric("quectel_watchdog_last_recovery_duration_seconds", "gauge")
    local actions_total     = metric("quectel_watchdog_actions_total", "counter")
    local consecutive_failed = metric("quectel_watchdog_consecutive_failed_actions", "gauge")
    local nr_detached_since = metric("quectel_watchdog_nr_detached_since_timestamp_seconds", "gauge")
    local alerted_failed    = metric("quectel_watchdog_alerted_failed", "gauge")
    local alerted_detach    = metric("quectel_watchdog_alerted_detach_long", "gauge")
    local updated           = metric("quectel_watchdog_updated_timestamp_seconds", "gauge")

    nr_attached({}, num("nr_attached"))
    nr_carriers({}, num("nr_carriers"))
    lte_carriers({}, num("lte_carriers"))
    nr_capable({}, num("nr_capable"))
    connected({}, num("connected"))
    consecutive({}, num("consecutive_degraded"))
    cooldown_until({}, num("cooldown_until"))
    last_action({}, num("last_action_ts"))
    last_recovery({}, num("last_recovery_seconds"))
    actions_total({ stage = "mode_toggle" }, num("actions_total_mode_toggle"))
    actions_total({ stage = "bearer_reconnect" }, num("actions_total_bearer_reconnect"))
    consecutive_failed({}, num("consecutive_failed_actions"))
    nr_detached_since({}, num("nr_detached_since"))
    alerted_failed({}, num("alerted_failed"))
    alerted_detach({}, num("alerted_detach_long"))
    updated({}, num("updated_ts"))
end

return { scrape = scrape }
