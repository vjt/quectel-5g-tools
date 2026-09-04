--- Decides whether a 5g-watchdog recovery attempt is worth making.
--
-- The watchdog has exactly one recovery action, bearer_reconnect: an
-- ifdown/ifup of the wwan interface, which tears down the PDN bearer and
-- builds a fresh one. That fixes a bearer stuck without its NR secondary
-- carrier, which is the failure it was written for (2026-05-04, where
-- three mode_toggles and a COPS toggle all failed and the bearer bounce
-- recovered NR in seconds on the same n78 cell).
--
-- It cannot fix a bad LTE anchor. On 2026-09-04 at 04:05 the modem
-- reselected from B1 pci 34 — which grants EN-DC and was carrying n78
-- pci 920 — onto B3 pci 427, which does not. Rebuilding the bearer
-- against the same anchor produces the same anchor. The watchdog spent
-- the day proving it: 30 bearer bounces, each dropping every connection
-- through the router and changing its public IP, none of which could
-- have worked. It could not tell the two failures apart because probe()
-- reduced the modem's view to carrier *counts* and discarded the one
-- fact that distinguishes them — which cell the modem is camped on.
--
-- So the rule is: an action is worth one attempt per anchor. Fail on an
-- anchor and that anchor is spent; wait for the cell to hand back a
-- different one, which is a new hypothesis and worth another attempt.
-- Suppression is always keyed on the anchor and never becomes a blanket
-- "stop trying" — the point is to stop *useless* actions, not useful
-- ones, because LTE-only is a degraded line and does warrant recovery.

local M = {}

--- Identify the LTE anchor from a parsed carrier-aggregation table.
-- The identity is ARFCN plus PCI: a PCI is only unique within a
-- frequency, so PCI alone would make two different cells compare equal.
-- @param ca table as returned by the QCAINFO parser (pcc + scc list)
-- @return identity string and a human-readable label, or nil if there is
--   no primary carrier (no service — a different failure entirely)
function M.anchor_of(ca)
    if not ca or not ca.pcc then return nil end
    local pcc = ca.pcc
    if not pcc.arfcn or not pcc.pci then return nil end

    local identity = string.format("%d:%d", pcc.arfcn, pcc.pci)
    local prefix = (pcc.rat == "5g") and "n" or "B"
    local label = string.format("%s%s p%d", prefix,
                                tostring(pcc.band or "?"), pcc.pci)
    return identity, label
end

--- Decide whether to run a recovery action now.
-- @param s table:
--   nr_attached   true when NR is already up
--   anchor        current anchor identity (from anchor_of)
--   failed_anchor anchor on which the last action failed, or nil
-- @return boolean, and the reason (for logging)
function M.should_act(s)
    if s.nr_attached then
        return false, "NR attached"
    end

    if not s.anchor then
        -- No primary carrier at all. That is loss of service, not an
        -- anchor without EN-DC, and bouncing the bearer here would be
        -- guesswork against a modem that has nothing to bounce.
        return false, "no serving cell"
    end

    if s.failed_anchor and s.failed_anchor == s.anchor then
        return false, string.format(
            "anchor %s unchanged since the last failed action — "
            .. "a bearer rebuild cannot change which cell we are on",
            s.anchor)
    end

    return true, "anchor not yet tried"
end

return M
