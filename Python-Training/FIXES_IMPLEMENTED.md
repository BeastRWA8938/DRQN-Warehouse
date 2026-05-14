# Reward System Fixes - Implementation Summary

**Date:** May 11, 2026  
**File Modified:** GridAgent.cs  
**Status:** ✅ COMPLETE

---

## Fixes Implemented

### ✅ FIX #1: Reverse Movement Penalty Reduced (CRITICAL)

**Change:**
```csharp
BEFORE: private const float MinReverseMovePenalty = 0.75f;
AFTER:  private const float MinReverseMovePenalty = 0.20f;
```

**Impact:**
- Reverse movement now costs -0.20 instead of -0.75
- Agent net reward for tactical reverse: **-0.042** (slightly negative but usable)
- Rotation-Rotate-Forward workaround now costs **+0.058** (more expensive than reverse)
- **Result:** Agent prefers reverse for backward movement, not multi-step rotation workarounds

**Mathematical Validation:**
```
Action: Move 1 cell backward via reverse
Cost = -0.05 (base) - 0.20 (reverse) + 0.208 (PBRS) = -0.042

Action: Move 1 cell backward via Rotate-Rotate-Forward
Cost = -0.05 - 0.05 - 0.05 + 0.208 = +0.058

Reverse is now more efficient than the workaround ✓
```

---

### ✅ FIX #2: Collision Penalty Asymmetry Removed (HIGH)

**Change:**
```csharp
BEFORE:
    else if (gridManager.IsCellOccupiedByOtherAgent(nextPos, this))
    {
        stepReward -= InvalidMovePenalty;  // Extra -1.0
        AddReward(stepReward);
        gridManager.HandleAgentCollision(this, ...);
        return;
    }

AFTER:
    else if (gridManager.IsCellOccupiedByOtherAgent(nextPos, this))
    {
        // stepReward -= InvalidMovePenalty;  // REMOVED
        gridManager.HandleAgentCollision(this, ...);
        return;
    }
```

**Impact:**
- **Before:** Agent A: -26.0 (Invalid -1 + Collision -25), Agent B: -25.0 (Only collision)
- **After:** Agent A: -25.0 (Collision), Agent B: -25.0 (Collision)
- **Result:** Equal penalty for both agents, no incentive to be passive/standstill

**Prevents:** Agents learning to block and let others crash into them

---

### ✅ FIX #7: Rotation Cost Increased (SECONDARY)

**Change:**
```csharp
BEFORE: stepReward -= 0.05f;  // Base step penalty
AFTER:  stepReward -= RotationBaseCost;  // 0.10f

WHERE: private const float RotationBaseCost = 0.10f;
```

**Impact:**
- Rotation now costs -0.10 instead of -0.05
- Makes rotation twice as expensive as before
- Discourages "spin in place" behavior
- Works in tandem with Fix #1 to prevent rotation workarounds

**Cost comparison:**
```
Rotation: -0.10 (now more expensive)
Forward:  -0.05 + 0.208 PBRS = +0.158 (still preferable)
Reverse:  -0.05 - 0.20 + 0.208 = -0.042 (now viable)
```

---

### ✅ FIX #4: Defensive Empty Dropzone Penalty (OPTIONAL)

**Change:**
```csharp
// Added in DeliverCargo phase:
else if (currentGridPos == gridManager.deliveryLocation && !hasCargo)
{
    stepReward -= emptyDropzonePenalty;
    if (statsManager != null) statsManager.RecordEmptyDrop();
}
```

**Impact:**
- Defensive check for edge case (shouldn't occur in normal play)
- If agent is at delivery location without cargo in DeliverCargo phase, penalize
- Makes reward structure more consistent and explicit

**Probability:** This scenario is extremely rare (cargo can't be lost mid-delivery in current design)

---

## Testing Recommendations

### Priority 1: Reverse Movement Behavior
**Verify:** Agent uses reverse movement tactically (for coordination, collision avoidance) but doesn't abuse it
- Monitor action frequencies in TensorBoard
- Check if reverse is used < 10% of the time (tactical only)
- Verify forward movement remains dominant

### Priority 2: Collision Avoidance
**Verify:** Both agents actively avoid collisions rather than one going passive
- Monitor collision rate (should decrease over time)
- Check if both agents have similar learning curves
- Ensure no "standing still" dominance patterns

### Priority 3: Rotation Usage
**Verify:** Agents prefer direct paths over rotation workarounds
- Monitor rotation frequency (should be rare)
- Check efficiency metrics improve
- Verify forward movement is still preferred over rotate+forward

---

## Reward Schedule (Updated)

### Movement Costs
| Action | Cost | PBRS (1 cell closer) | Net |
|--------|------|-----|-----|
| Forward | -0.05 | +0.208 | **+0.158** ✓ |
| Reverse | -0.05 | -0.20 | +0.208 | **-0.042** |
| Rotate | -0.10 | 0 | **-0.10** |
| Rotate-Rotate-Forward | -0.10-0.10-0.05 | +0.208 | **+0.058** |

**Key:** Forward is always best, reverse is now viable for tactical use, rotation is discouraged.

### Penalty Summary
| Event | Cost | When |
|-------|------|------|
| Base step | -0.05 | Every movement |
| Reverse | -0.20 | Moving backward (FIX #1) |
| Rotation | -0.10 | Turning (FIX #7) |
| Invalid move (OOB) | -1.0 | Out of bounds |
| Rack hit | -15.0 | At spawn location |
| Empty dropzone | -12.0 | At delivery without cargo (FIX #4) |
| Collision | -25.0 | Both agents hit equally (FIX #2) |

### Reward Summary
| Event | Reward | When |
|-------|--------|------|
| Pickup cargo | +15.0 | At cargo location while seeking |
| Deliver cargo | +50.0 | At delivery location with cargo |

---

## Code Locations

| Fix | File | Line | Change |
|-----|------|------|--------|
| #1 | GridAgent.cs | 14 | MinReverseMovePenalty: 0.75 → 0.20 |
| #7 | GridAgent.cs | 15 | New const: RotationBaseCost = 0.10f |
| #7 | GridAgent.cs | 188 | Rotation penalty: 0.05 → RotationBaseCost |
| #2 | GridAgent.cs | 212-218 | Removed InvalidMovePenalty from collision |
| #4 | GridAgent.cs | 277-281 | Added defensive penalty in DeliverCargo |

---

## Notes for Future Training

1. **Monitor Learning Curve:** These changes will affect training dynamics. Expect:
   - Faster convergence for reverse/tactical movement
   - More active collision avoidance
   - Different epsilon schedules may be needed

2. **Checkpoint Comparison:** Old checkpoints (with 0.75 reverse penalty) may not transfer well to new penalty structure. Consider:
   - Starting fresh training with new penalties
   - Or gradual penalty adjustment during resume

3. **Multi-Agent Dynamics:** Fix #2 (collision symmetry) may change multi-agent coordination patterns. This is good - encourages active cooperation rather than passive standoff.

4. **Future Tuning:** If needed, fine-tune:
   - Reverse penalty: 0.20 is still somewhat negative; could go up to 0.25 if reverse is used too much
   - Rotation cost: 0.10 is twice the original; could adjust if rotation behavior needs tweaking
   - Empty dropzone: 12.0 is defensive; could reduce if edge case becomes issue

---

## Summary

✅ **All 4 fixes implemented successfully**
- Reverse penalty optimized for tactical use
- Collision penalties equalized between agents
- Rotation cost increased to prevent workarounds
- Defensive penalty added for edge cases

**Expected Training Improvement:** More efficient policies, better multi-agent coordination, no reward exploitation workarounds.
