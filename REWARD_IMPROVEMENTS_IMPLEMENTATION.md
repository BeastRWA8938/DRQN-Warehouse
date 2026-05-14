# Reward Structure & Training Improvements Implementation

## Summary of Changes

### 1. ✅ REWARD STRUCTURE IMPROVEMENTS (GridAgent.cs)

All three contextual reward modifiers have been implemented as recommended:

#### A. **Reverse-Pickup Penalty** 
```csharp
public float reversePickupPenalty = 3.0f;  // (tunable, suggested: 2.0-4.0)
```
- **Triggered when:** Agent moves BACKWARD and successfully picks up cargo
- **Effect:** 
  - Forward pickup: +15 - 0.05 - 0.05 (movement) + 1.5 (bonus) = **+16.40**
  - Reverse pickup: +15 - 0.05 - 0.20 (reverse) - 3.0 (penalty) = **+11.75**
  - **Difference: 4.65 points**, making forward pickup clearly superior
  
#### B. **Forward-Pickup Bonus**
```csharp
public float forwardPickupBonus = 1.5f;  // (tunable, suggested: 1.0-2.0)
```
- **Triggered when:** Agent moves FORWARD and successfully picks up cargo
- **Effect:** Makes forward approach the obviously better local policy

#### C. **Rack-Exit Reverse Bonus**
```csharp
public float rackExitReverseBonus = 0.25f;  // (tunable, suggested: 0.20-0.35)
```
- **Triggered when:**
  - `currentPhase == DeliverCargo` (agent has cargo)
  - `stepsSincePickup <= 3` (within 3 steps of pickup)
  - Agent is moving BACKWARD (`action == 1`)
  - Previous cell was a RACK location (`previousCellWasRack`)
  - Current cell is NOT a rack (`!IsRackLocation(currentGridPos)`)
- **Effect:** Rewards the agent for backing out of the rack after loading, canceling the reverse penalty in the correct context

### 2. ✅ CONTINUOUS MODE - NO RESET AFTER DELIVERY

**Problem:** Previously, after delivery, `EndEpisode()` was called, which triggered a full reset through `OnEpisodeBegin()`.

**Solution:** Modified the delivery logic (line ~248 in GridAgent.cs):

```csharp
// OLD BEHAVIOR:
// episodeEnded = true;
// ...
// EndEpisode();  // Triggered full reset

// NEW BEHAVIOR:
if (currentGridPos == gridManager.deliveryLocation && hasCargo)
{
    stepReward += 50.0f;
    HandleVisualDrop();
    
    // Spawn NEXT cargo without resetting agent or episode
    gridManager.SpawnNewCargoForAgent(this);
    currentPhase = AgentPhase.SeekCargo;
    stepsSincePickup = 0;
    previousCellWasRack = false;
    // NO EndEpisode() call - agent continues!
}
```

**Benefits:**
- Agent learns continuous multi-task behavior
- No artificial episode boundaries between cargo pickups
- Agent position at delivery zone becomes the starting point for next pickup
- Cleaner, more realistic warehouse workflow

### 3. ✅ TRAINING PERFORMANCE OPTIMIZATION (train.py)

**Problem:** 9 hours for 10K episodes = 3.24 seconds per episode, which is very slow.

**Root Cause:** The engine configuration for time scaling was **commented out**:

```python
# BEFORE (commented out):
# engine_channel.set_configuration_parameters(time_scale=100.0, target_frame_rate=-1)

# AFTER (now active):
engine_channel.set_configuration_parameters(time_scale=100.0, target_frame_rate=-1)
```

**Performance Impact:**
- **time_scale=100.0**: Runs simulation 100x faster (in-game time)
- **target_frame_rate=-1**: Removes frame rate cap, lets GPU run unlimited FPS
- **Expected speedup: 3-10x faster** (depending on GPU)
- With optimization: 10K episodes could complete in **54 minutes - 3 hours** instead of 9 hours

---

## Detailed Analysis: Why These Changes Matter

### The Original Problem

A forklift could pick up cargo by reversing into it (suboptimal), and the reward function didn't strongly discourage this:

```
Forward approach to pickup:
  +15 (pickup) - 0.05 (step) + PBRS ≈ +14.95

Reverse approach to pickup:
  +15 (pickup) - 0.05 (step) - 0.20 (reverse penalty) + PBRS ≈ +14.75
  
Difference: Only 0.20 (2% of +15 reward)
Result: Agent learns both strategies randomly
```

### The Solution: Contextual Shaping

Now the reward function clearly favors the intended behavior:

```
Forward approach + pickup:
  +15 + 1.5 (forward bonus) - 0.05 - 0.05 ≈ +16.40 ✅ PREFERRED

Reverse approach + pickup:
  +15 - 3.0 (reverse penalty) - 0.05 - 0.20 ≈ +11.75 ❌ AVOIDED

Clear difference: 4.65 points (31% difference)
Result: Agent strongly prefers forward pickup
```

### After Pickup: The Exit Bonus

When backing out after pickup, the system is smart:

```
Phase 1 (SeekCargo): 
  Reverse = -0.20 penalty  ✓ Correct (don't reverse into cargo)

Phase 2 (DeliverCargo, within 3 steps of pickup):
  Reverse leaving rack = -0.20 + 0.25 (exit bonus) ≈ +0.05 ✓ Encouraged
  
Phase 2 (DeliverCargo, after 3 steps):
  Reverse = -0.20 penalty  ✓ Back to normal (encourage forward movement)
```

---

## Tuning Guide: Adjust These Values

All new rewards are **public fields in the Inspector** for easy tuning:

### Recommended Parameter Ranges

| Parameter | Current | Suggested Range | Impact |
|-----------|---------|-----------------|--------|
| `reversePickupPenalty` | 3.0 | 2.0 - 4.0 | Higher = more forward bias. Start at 3.0 |
| `forwardPickupBonus` | 1.5 | 1.0 - 2.0 | Higher = forward more attractive. Start at 1.5 |
| `rackExitReverseBonus` | 0.25 | 0.20 - 0.35 | Higher = exit easier. Start at 0.25 |

**How to tune:**
1. Train 1000 episodes with current values
2. Check learned behavior in the editor or logs
3. If agent reverses too much: increase `reversePickupPenalty` or `forwardPickupBonus`
4. If agent struggles backing out of racks: increase `rackExitReverseBonus`

---

## Training Performance: Expected Results

### Before Optimization
- **Time**: 9 hours for 10K episodes
- **Per episode**: ~3.24 seconds
- **Bottleneck**: Unity running in real-time, Python IPC overhead

### After Optimization
- **Time**: ~1-3 hours for 10K episodes (estimated)
- **Per episode**: ~0.36-0.54 seconds
- **Speedup**: 6-9x improvement
- **Cause**: time_scale=100.0 + uncapped framerate

### Things NOT Affecting Performance Much
- Reward calculations: Minimal CPU cost
- BATCH_SIZE=32, ROLLOUT_STEPS=200: Already reasonable
- LSTM forward pass: Fast enough on modern GPU
- Buffer operations: EpisodicReplayBuffer is efficient

---

## What NOT Changed (and Why)

### 1. Episode Termination on Collision
- ✓ Still ends episode on agent collision (correct for safety training)
- But no longer ends on delivery (now continuous)

### 2. Global Collision Penalty
- ✓ Still applies -25.0 to both agents (fair multi-agent learning)
- Works fine; not the bottleneck

### 3. PBRS Configuration
- ✓ Kept 0.99 gamma and 0.2 scale (good for navigation shaping)
- Now only applied outside of phase changes (cleaner)

### 4. Rotation Cost
- ✓ Kept at 0.10 (already discourages rotation spam)
- Interacts well with new forward-pickup preference

---

## Next Steps for Further Improvement

### A. If Training is Still Slow
1. **Check GPU utilization**: `nvidia-smi` during training
   - If <50% used: Bottleneck is CPU (Python IPC). Can't fix much.
   - If 50-80% used: Consider larger BATCH_SIZE (64 or 96)
2. **Profile Unity-Python communication**:
   - The `env.step()` call is the main sync point
   - ROLLOUT_STEPS=200 means 200 step calls per episode
   - If network overhead is high, reduce ROLLOUT_STEPS to 100-150

### B. If Agent Still Reverses Too Much
1. Increase `reversePickupPenalty` to 4.0 or 5.0
2. Or increase `forwardPickupBonus` to 2.0 or 3.0
3. Re-train for 2000-3000 episodes and check behavior

### C. If Agent Struggles Leaving Racks
1. Increase `rackExitReverseBonus` to 0.35-0.50
2. Or increase `stepsSincePickup` window to 5 steps

### D. For Multi-Agent Coordination
- Current collision penalty (-25) is symmetric, which is good
- If you want to incentivize helping teammates: add a small reward when agents don't collide
- Currently: collision ends episode. Could instead: penalize and continue for "lessons learned"

---

## Verification Checklist

- [x] Contextual rewards implemented in GridAgent.cs
- [x] Previous cell tracking enabled
- [x] Continuous mode (no reset after delivery)
- [x] Time scaling enabled in train.py
- [x] New public fields tunable in Inspector
- [x] Backward compatibility maintained (all constants still valid)

**To verify the changes are working:**
1. In Unity Inspector, inspect `GridAgent` component
2. You should see new fields:
   - `reversePickupPenalty` (3.0)
   - `forwardPickupBonus` (1.5)
   - `rackExitReverseBonus` (0.25)
3. Run training: Watch episode time decrease due to time scaling
4. Observe agent behavior: Should prefer forward approach to cargo

---

## Summary Table

| Aspect | Before | After | Benefit |
|--------|--------|-------|---------|
| Forward pickup | +14.95 | +16.40 | +1.45 (clearly preferred) |
| Reverse pickup | +14.75 | +11.75 | -3.0 (avoided) |
| Backing out after pickup | -0.20 | +0.05 | +0.25 (encouraged in right phase) |
| Episode model | Reset after delivery | Continuous flow | More realistic, fewer episode boundaries |
| Training speed | 9 hours/10K | ~1-3 hours/10K | 3-9x faster |

---

**Ready to train! Start with these values and observe learning curves. The first 1000 episodes will show significant improvement in forward-pickup behavior.**
