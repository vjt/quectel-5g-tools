-- Signal quality thresholds for visual feedback

local M = {}

-- Signal quality levels
M.EXCELLENT = "excellent"
M.GOOD = "good"
M.FAIR = "fair"
M.POOR = "poor"

-- RSRP thresholds (dBm) - Reference Signal Received Power
local RSRP_EXCELLENT = -80
local RSRP_GOOD = -90
local RSRP_FAIR = -100

-- RSRQ thresholds (dB) - Reference Signal Received Quality
local RSRQ_EXCELLENT = -10
local RSRQ_GOOD = -12
local RSRQ_FAIR = -15

-- SINR thresholds (dB) - Signal to Interference & Noise Ratio
local SINR_EXCELLENT = 20
local SINR_GOOD = 13
local SINR_FAIR = 0

--- Get RSRP quality level
-- @param rsrp RSRP value in dBm
-- @return Quality level string
function M.rsrp_quality(rsrp)
    if not rsrp then return nil end
    if rsrp >= RSRP_EXCELLENT then return M.EXCELLENT end
    if rsrp >= RSRP_GOOD then return M.GOOD end
    if rsrp >= RSRP_FAIR then return M.FAIR end
    return M.POOR
end

--- Get RSRQ quality level
-- @param rsrq RSRQ value in dB
-- @return Quality level string
function M.rsrq_quality(rsrq)
    if not rsrq then return nil end
    if rsrq >= RSRQ_EXCELLENT then return M.EXCELLENT end
    if rsrq >= RSRQ_GOOD then return M.GOOD end
    if rsrq >= RSRQ_FAIR then return M.FAIR end
    return M.POOR
end

--- Get SINR quality level
-- @param sinr SINR value in dB
-- @return Quality level string
function M.sinr_quality(sinr)
    if not sinr then return nil end
    if sinr >= SINR_EXCELLENT then return M.EXCELLENT end
    if sinr >= SINR_GOOD then return M.GOOD end
    if sinr >= SINR_FAIR then return M.FAIR end
    return M.POOR
end

--- Get overall signal quality (based on SINR primarily)
-- @param rsrp RSRP value
-- @param rsrq RSRQ value
-- @param sinr SINR value
-- @return Quality level string
function M.overall_quality(rsrp, rsrq, sinr)
    -- SINR is the most important for data performance
    if sinr then
        return M.sinr_quality(sinr)
    end
    -- Fall back to RSRP
    if rsrp then
        return M.rsrp_quality(rsrp)
    end
    -- Last resort RSRQ
    if rsrq then
        return M.rsrq_quality(rsrq)
    end
    return nil
end

--- Calculate beep interval based on SINR
-- Higher SINR = faster beeps
-- @param sinr SINR value in dB
-- @return Interval in seconds (or nil to disable beeps)
function M.beep_interval(sinr)
    if not sinr then return nil end

    -- Map SINR to beep interval
    -- SINR < 0: no beeps
    -- SINR 0-10: slow beeps (1.0 - 0.5s)
    -- SINR 10-20: medium beeps (0.5 - 0.2s)
    -- SINR > 20: fast beeps (0.2 - 0.1s)

    if sinr < 0 then
        return nil  -- no beeps for poor signal
    elseif sinr < 10 then
        return 1.0 - (sinr / 10) * 0.5  -- 1.0 to 0.5
    elseif sinr < 20 then
        return 0.5 - ((sinr - 10) / 10) * 0.3  -- 0.5 to 0.2
    else
        local interval = 0.2 - ((sinr - 20) / 20) * 0.1
        return math.max(interval, 0.1)  -- cap at 0.1s
    end
end

--- Calculate number of beeps based on SINR
-- Better signal = more beeps for audio feedback while pointing antenna
-- @param sinr SINR value in dB
-- @return Number of beeps (0-4), or nil to disable
function M.beep_count(sinr)
    if not sinr then return nil end

    -- Map SINR to beep count
    -- SINR < 0: no beeps (poor)
    -- SINR 0-10: 1 beep (fair)
    -- SINR 10-20: 2 beeps (good)
    -- SINR 20-30: 3 beeps (excellent)
    -- SINR > 30: 4 beeps (outstanding)

    if sinr < 0 then
        return 0
    elseif sinr < 10 then
        return 1
    elseif sinr < 20 then
        return 2
    elseif sinr < 30 then
        return 3
    else
        return 4
    end
end

return M
