# ONNX Model Export & Unity Barracuda Integration Guide

## Overview

The modified training pipeline now exports trained DRQN models to ONNX format alongside checkpoint saves. This allows you to import the models directly into Unity and use them with the Barracuda inference engine.

## What Changed

### Files Modified
1. **drqn_model.py**
   - Added `DRQNForONNX` wrapper class for proper LSTM state handling
   - Added `export_model_to_onnx()` function for ONNX export
   - Maintained original DRQN architecture (no changes to training flow)

2. **train.py**
   - Imported ONNX export function
   - Added automatic ONNX export whenever checkpoints are saved
   - Each checkpoint now has a companion `.onnx` file

### Backward Compatibility
- ✅ All existing `.pth` checkpoints are still saved
- ✅ Training code is unchanged
- ✅ Model architecture is identical
- ✅ Only adds ONNX export as an additional output

---

## ONNX Export Details

### File Structure
After training, your `checkpoints/` folder will contain:
```
checkpoints/
├── drqn_ep1000_gamma0.99_eps0.10_mem76800.pth   (PyTorch checkpoint)
├── drqn_ep1000_gamma0.99_eps0.10_mem76800.onnx  (ONNX model) ← USE THIS IN UNITY
├── drqn_ep2000_gamma0.99_eps0.08_mem142000.pth
├── drqn_ep2000_gamma0.99_eps0.08_mem142000.onnx ← Latest version
...
```

### ONNX Model Signature

**Inputs:**
| Input Name | Shape | Type | Description |
|---|---|---|---|
| `state` | (batch=1, seq=1, 14) | float32 | Current observation |
| `hidden_state` | (batch=1, 64) | float32 | LSTM hidden state from previous timestep |
| `cell_state` | (batch=1, 64) | float32 | LSTM cell state from previous timestep |

**Outputs:**
| Output Name | Shape | Type | Description |
|---|---|---|---|
| `q_values` | (batch=1, seq=1, 4) | float32 | Q-values for 4 actions |
| `hidden_state_out` | (batch=1, 64) | float32 | Updated hidden state for next timestep |
| `cell_state_out` | (batch=1, 64) | float32 | Updated cell state for next timestep |

---

## How to Use in Unity

### Step 1: Import the ONNX Model
1. Copy your trained `.onnx` file to your Unity project
   ```
   Assets/
   ├── AI/
   │   ├── Models/
   │   │   └── drqn_ep2000_gamma0.99_eps0.08_mem142000.onnx
   ```

2. In the Inspector, set **Model Executor** to **Barracuda** (or Sentis if using newer versions)

3. Set **Data Types** to **Float32**

### Step 2: Create a C# Agent Script

```csharp
using UnityEngine;
using Unity.Barracuda;

public class DRQNAgentInference : MonoBehaviour
{
    // ====== Configuration ======
    public NNModel onnxModel;
    private IWorker worker;
    private const int INPUT_SIZE = 14;
    private const int HIDDEN_SIZE = 64;
    private const int NUM_ACTIONS = 4;
    
    // ====== LSTM State Storage ======
    private float[] hiddenState;      // Shape: [1, HIDDEN_SIZE]
    private float[] cellState;        // Shape: [1, HIDDEN_SIZE]
    
    void Start()
    {
        // Load and prepare the model
        var model = ModelLoader.Load(onnxModel);
        worker = WorkerFactory.CreateWorker(WorkerFactory.Type.ComputePrecompiled, model);
        
        // Initialize LSTM states to zeros
        hiddenState = new float[1 * HIDDEN_SIZE];
        cellState = new float[1 * HIDDEN_SIZE];
    }
    
    /// <summary>
    /// Get action from the DRQN model
    /// </summary>
    public int GetAction(float[] observation, bool useEpsilonGreedy = false, float epsilon = 0.1f)
    {
        if (observation.Length != INPUT_SIZE)
        {
            Debug.LogError($"Expected observation size {INPUT_SIZE}, got {observation.Length}");
            return 0;
        }
        
        // ====== Prepare Input Tensors ======
        
        // State: reshape to (1, 1, 14)
        Tensor stateTensor = new Tensor(new Shape(1, 1, INPUT_SIZE), observation);
        
        // Hidden state: (1, 64)
        Tensor hiddenTensor = new Tensor(new Shape(1, HIDDEN_SIZE), hiddenState);
        
        // Cell state: (1, 64)
        Tensor cellTensor = new Tensor(new Shape(1, HIDDEN_SIZE), cellState);
        
        // ====== Run Inference ======
        worker.Execute(new Dictionary<string, Tensor>
        {
            { "state", stateTensor },
            { "hidden_state", hiddenTensor },
            { "cell_state", cellTensor }
        });
        
        // ====== Extract Outputs ======
        var qValuesTensor = worker.PeekOutput("q_values");         // Shape: (1, 1, 4)
        var hiddenOutTensor = worker.PeekOutput("hidden_state_out"); // Shape: (1, 64)
        var cellOutTensor = worker.PeekOutput("cell_state_out");     // Shape: (1, 64)
        
        // Read Q-values (last timestep, all actions)
        float[] qValues = qValuesTensor.AsFloats();
        // qValues is shape (1, 1, 4), so we need the last 4 values
        float[] currentQValues = new float[NUM_ACTIONS];
        System.Array.Copy(qValues, qValues.Length - NUM_ACTIONS, currentQValues, 0, NUM_ACTIONS);
        
        // Update LSTM state for next timestep
        hiddenState = hiddenOutTensor.AsFloats();
        cellState = cellOutTensor.AsFloats();
        
        // ====== Select Action ======
        int action;
        if (useEpsilonGreedy && Random.value < epsilon)
        {
            // Epsilon-greedy: random exploration
            action = Random.Range(0, NUM_ACTIONS);
            Debug.Log($"[DRQN] Epsilon-greedy action: {action}");
        }
        else
        {
            // Greedy: select best action
            action = GetArgMax(currentQValues);
            Debug.Log($"[DRQN] Greedy action: {action} | Q-values: [{string.Join(", ", System.Array.ConvertAll(currentQValues, x => x.ToString("F3")))}]");
        }
        
        // ====== Cleanup ======
        stateTensor.Dispose();
        hiddenTensor.Dispose();
        cellTensor.Dispose();
        
        return action;
    }
    
    /// <summary>
    /// Reset LSTM hidden and cell states (call when episode starts)
    /// </summary>
    public void ResetState()
    {
        System.Array.Clear(hiddenState, 0, hiddenState.Length);
        System.Array.Clear(cellState, 0, cellState.Length);
        Debug.Log("[DRQN] LSTM state reset");
    }
    
    private int GetArgMax(float[] values)
    {
        int maxIdx = 0;
        float maxVal = values[0];
        for (int i = 1; i < values.Length; i++)
        {
            if (values[i] > maxVal)
            {
                maxVal = values[i];
                maxIdx = i;
            }
        }
        return maxIdx;
    }
    
    void OnDestroy()
    {
        worker?.Dispose();
    }
}
```

### Step 3: Use in Your Game

```csharp
public class WarehouseAgent : MonoBehaviour
{
    public DRQNAgentInference drqnAgent;
    private float[] currentObservation;
    
    void Start()
    {
        drqnAgent = GetComponent<DRQNAgentInference>();
    }
    
    void Update()
    {
        // Gather observation from environment (14 values)
        currentObservation = GatherObservation(); // Your implementation
        
        // Get action from DRQN
        int action = drqnAgent.GetAction(currentObservation, useEpsilonGreedy: true, epsilon: 0.05f);
        
        // Execute action in your game
        ExecuteAction(action);
    }
    
    void OnEpisodeStart()
    {
        // Reset LSTM states at the beginning of each episode
        drqnAgent.ResetState();
    }
    
    private float[] GatherObservation()
    {
        // Example: return 14 float observations
        // This should match the state space used in training
        return new float[14] 
        { 
            // Your observation values here
        };
    }
    
    private void ExecuteAction(int action)
    {
        // Map action to movement/behavior
        // action: 0-3 (whatever your 4 discrete actions are)
    }
}
```

---

## Important Notes

### 🔴 LSTM State Management
- **CRITICAL**: You MUST maintain hidden and cell states across timesteps
- Reset states when an episode starts (agent dies, level restarts, etc.)
- Do NOT discard states between consecutive frames
- If states become unstable, reset to zeros

### ⚠️ Observation Format
- Your observation MUST be exactly 14 float values
- Same feature order as training input
- Normalize values if needed (should match training preprocessing)

### 📊 Dynamic vs Fixed Shape
The ONNX model uses dynamic batch size, but we always use batch=1 in Unity. If you need to process multiple agents in parallel, you can:
- Run inference serially (simpler, slower)
- Batch multiple agents together (more complex, faster)

### 🎯 Action Selection
- Default: Greedy (best Q-value)
- Alternative: Epsilon-greedy for exploration during gameplay
- Can anneal epsilon over time

### 💾 Checkpoint Selection
- Use the LATEST `.onnx` file for best performance
- Or select based on reward metrics from training logs

---

## Troubleshooting

### Model Loading Fails
- ✓ Verify ONNX file is not corrupted: `python -c "import onnx; onnx.checker.check_model('model.onnx')"`
- ✓ Check Barracuda version supports opset 14
- ✓ Ensure model is in correct folder hierarchy

### Q-values are NaN/Inf
- ✓ Check observation values are reasonable
- ✓ Verify hidden/cell states are initialized
- ✓ Check for model overfitting during training

### Inference is Slow
- ✓ Use GPU worker: `WorkerFactory.Type.ComputePrecompiled`
- ✓ Reduce model complexity if needed
- ✓ Profile with Unity Profiler

### Actions are Random
- ✓ Verify observation is correct
- ✓ Check model was trained on same observation space
- ✓ Ensure LSTM states are persisted between frames

---

## Performance Tips

1. **Cache the worker**: Don't recreate on every inference
2. **Use fixed timestep**: Consistent frame timing improves learning
3. **Batch observations**: If multiple agents, process together
4. **Monitor memory**: LSTM states take 128 floats per agent

---

## References

- Barracuda Docs: https://docs.unity3d.com/Packages/com.unity.barracuda@latest/
- ONNX Spec: https://onnx.ai/
- DRQN Paper: https://arxiv.org/abs/1507.06527
