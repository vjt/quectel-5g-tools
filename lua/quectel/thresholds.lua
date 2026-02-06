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

--- Calculate number of beeps based on SINR
-- Better signal = more beeps for audio feedback while pointing antenna
-- Matches legacy Python implementation thresholds
-- @param sinr SINR value in dB
-- @return Number of beeps (0-6)
function M.beep_count(sinr)
    if not sinr then return 0 end

    -- Map SINR to beep count (from legacy Python)
    -- SINR >= 19: 6 beeps
    -- SINR >= 18: 5 beeps
    -- SINR >= 17: 4 beeps
    -- SINR >= 16: 3 beeps
    -- SINR >= 14: 2 beeps
    -- SINR >= 12: 1 beep
    -- SINR < 12: no beeps

    if sinr >= 19 then
        return 6
    elseif sinr >= 18 then
        return 5
    elseif sinr >= 17 then
        return 4
    elseif sinr >= 16 then
        return 3
    elseif sinr >= 14 then
        return 2
    elseif sinr >= 12 then
        return 1
    else
        return 0
    end
end

return M
