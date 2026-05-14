# Python Training - DRQN with ONNX Export

Deep Reinforcement Q-Network (DRQN) training for the Warehouse simulation with automatic ONNX model export for Unity Barracuda integration.

## 📁 Files Overview

### Core Training
- **`train.py`** - Main training loop with automatic ONNX export
- **`drqn_model.py`** - DRQN architecture + ONNX export utilities
- **`replay_buffer.py`** - Episodic replay buffer for DRQN training

### Utilities
- **`export_checkpoint_to_onnx.py`** - Standalone script to export existing checkpoints (for backwards compatibility)

### Documentation
- **`MODIFICATION_SUMMARY.md`** - What was changed and why
- **`ONNX_UNITY_GUIDE.md`** - Complete guide for using exported models in Unity
- **`README.md`** - This file

---

## 🚀 Quick Start

### 1. Training

```bash
python train.py
```

**Modes available:**
- `MODE = "train"` - Start fresh training
- `MODE = "resume"` - Continue from existing checkpoint
- `MODE = "test"` - Run inference (no training)

**What happens:**
- Saves `.pth` checkpoints every ~10% of training
- **NEW**: Automatically exports companion `.onnx` files
- Logs metrics to TensorBoard

### 2. Output Files

Each checkpoint generates two files:
```
checkpoints/
├── drqn_ep1000_gamma0.99_eps0.10_mem76800.pth   ← PyTorch (for resuming training)
└── drqn_ep1000_gamma0.99_eps0.10_mem76800.onnx  ← ONNX (for Unity!) ✨
```

### 3. Using in Unity

1. Copy the `.onnx` file to your Unity project
2. Add `DRQNInferenceAgent.cs` component to your agent
3. Assign the ONNX model in the Inspector
4. Call `GetGreedyAction(observation)` or `GetExploratoryAction(observation, epsilon)`

See `ONNX_UNITY_GUIDE.md` for detailed integration steps.

---

## 📊 Training Configuration

Edit hyperparameters in `train.py`:

```python
# Key settings
MODE = "train"                    # train | resume | test
GAMMA = 0.99                      # Discount factor
LR = 1e-4                         # Learning rate
BATCH_SIZE = 32                   # Training batch size
SEQ_LEN = 10                      # Sequence length for DRQN
TOTAL_EPISODES = 10000            # Total training episodes
EPSILON_START = 1.0               # Initial exploration rate
EPSILON_MIN = 0.10                # Minimum exploration rate
```

---

## 🔧 Model Architecture

```
Input (observation: 14 values)
    ↓
[FC Layer: 14 → 64 + ReLU]
    ↓
[LSTM: 64 → 64]
    ↓
[FC Layer: 64 → 4 (Q-values)]
    ↓
Output (4 Q-values for discrete actions)
```

**LSTM State Handling:**
- Hidden state: 64 dimensions
- Cell state: 64 dimensions
- Persisted across timesteps within an episode
- Reset at episode boundaries

---

## 📦 ONNX Export Details

### What Gets Exported

The `DRQNForONNX` wrapper class converts the PyTorch model to ONNX with:
- **Input tensors**: state, hidden_state, cell_state
- **Output tensors**: q_values, hidden_state_out, cell_state_out
- **Opset version**: 14 (compatible with Barracuda)
- **Dynamic axes**: Supports variable batch sizes

### Export Function Signature

```python
export_model_to_onnx(
    model,                    # Trained DRQN model
    output_dir="checkpoints", # Where to save
    model_name="drqn_model"   # Name prefix
) → onnx_path
```

### Manual Export (for existing checkpoints)

```bash
# Export single checkpoint
python export_checkpoint_to_onnx.py checkpoints/drqn_ep1000.pth

# Export all checkpoints
python export_checkpoint_to_onnx.py checkpoints/ --batch

# Use GPU for faster export
python export_checkpoint_to_onnx.py checkpoints/drqn_ep1000.pth --device cuda
```

---

## 🎮 Unity Integration

### Minimal C# Example

```csharp
using UnityEngine;

public class Agent : MonoBehaviour
{
    public DRQNInferenceAgent drqn;
    
    void Start()
    {
        drqn.ResetEpisode();  // Reset LSTM state
    }
    
    void Update()
    {
        float[] observation = GetObservation();  // 14 values
        int action = drqn.GetGreedyAction(observation);
        DoAction(action);
    }
    
    float[] GetObservation()
    {
        // Return exactly 14 float values representing the current state
        return new float[14] { /* your observations */ };
    }
}
```

See `ONNX_UNITY_GUIDE.md` and `Assets/Scripts/DRQNInferenceAgent.cs` for complete examples.

---

## 📈 Monitoring Training

### TensorBoard

```bash
tensorboard --logdir runs/
```

Tracks:
- Total reward per episode
- Total steps per episode
- Average loss
- Epsilon decay
- Per-agent metrics

### Console Output

```
Ep 1000 | TotalR: 245.50 | Steps: 200 | Eps: 0.45 | A0: R=245.5, T=1
Ep 1001 | TotalR: 312.30 | Steps: 200 | Eps: 0.44 | A0: R=312.3, T=1
--> Saved Checkpoint: drqn_ep1000_gamma0.99_eps0.45_mem76800.pth
✓ ONNX Model exported: checkpoints/drqn_ep1000_gamma0.99_eps0.45_mem76800.onnx
```

---

## ⚙️ Environment Setup

### Requirements

```bash
pip install torch
pip install numpy
pip install mlagents_envs
```

### Unity Connection

Configure in `train.py`:

```python
# For training with compiled build
env_path = "Build/Warehouse.exe"
env = UnityEnvironment(file_name=env_path, no_graphics=True)

# For testing with Unity Editor (play in editor)
env = UnityEnvironment(file_name=None, seed=42)
```

---

## 💾 Checkpoint Format

### .pth Files (PyTorch)
```python
{
    'episode': int,                    # Training episode
    'model_state_dict': dict,          # Network weights
    'optimizer_state_dict': dict,      # Optimizer state (for resume)
    'epsilon': float                   # Exploration rate
}
```

### .onnx Files (ONNX Runtime)
- Binary format, optimized for inference
- No optimizer state (inference only)
- Ready for Unity/Barracuda

---

## 🔍 Debugging

### Check if ONNX export is working

```bash
python -c "import onnx; onnx.checker.check_model('checkpoints/model.onnx')"
```

### Verify model inputs/outputs

```bash
python -c "
import onnx
model = onnx.load('checkpoints/model.onnx')
for input_ in model.graph.input:
    print(f'Input: {input_.name}, Shape: {[d.dim_value for d in input_.type.tensor_type.shape.dim]}')
for output in model.graph.output:
    print(f'Output: {output.name}')
"
```

### Test inference in Python

```python
import torch
from drqn_model import DRQN

# Load checkpoint
checkpoint = torch.load('checkpoints/drqn_ep1000.pth')
model = DRQN()
model.load_state_dict(checkpoint['model_state_dict'])
model.eval()

# Test forward pass
state = torch.randn(1, 1, 14)
q_values, (h, c) = model(state, None)
print(f"Q-values shape: {q_values.shape}")
print(f"Hidden state shape: {h.shape}")
```

---

## 🚨 Common Issues

### Q: ONNX export fails with shape mismatch
**A:** Ensure the wrapper is receiving correct tensor shapes: (batch, seq_len, features)

### Q: Model inference is slow in Unity
**A:** Use GPU worker (`WorkerFactory.Type.ComputePrecompiled`) and batch operations

### Q: Q-values are NaN
**A:** Check observation values are reasonable; verify LSTM states are initialized

### Q: Can't find the ONNX file
**A:** Check `checkpoints/` directory; filename format is `drqn_ep{episode}_gamma{gamma}_eps{epsilon}_mem{memory}.onnx`

---

## 📚 References

- **DRQN Paper**: [Deep Recurrent Q-Learning for Partially Observable MDPs](https://arxiv.org/abs/1507.06527)
- **Barracuda Docs**: https://docs.unity3d.com/Packages/com.unity.barracuda@latest/
- **ONNX Spec**: https://onnx.ai/
- **PyTorch ONNX Export**: https://pytorch.org/docs/stable/onnx.html

---

## 📝 File Checklist

- [x] `train.py` - Training with ONNX export
- [x] `drqn_model.py` - Model + export utilities
- [x] `replay_buffer.py` - Experience replay
- [x] `export_checkpoint_to_onnx.py` - Manual export tool
- [x] `MODIFICATION_SUMMARY.md` - Technical changes
- [x] `ONNX_UNITY_GUIDE.md` - Complete integration guide
- [x] `DRQNInferenceAgent.cs` - Unity C# component
- [x] `README.md` - This file

---

## 🎯 Next Steps

1. **Train**: Run `python train.py` to start training (ONNX exports automatically)
2. **Monitor**: Check TensorBoard for training progress
3. **Select**: Choose best checkpoint based on reward/loss
4. **Export**: Latest checkpoint has matching `.onnx` file
5. **Integrate**: Follow `ONNX_UNITY_GUIDE.md` for Unity setup
6. **Deploy**: Add `DRQNInferenceAgent.cs` to your game objects

---

## 💡 Tips

- Use `MODE = "test"` to run inference without training
- Checkpoints save every ~10% of training; adjust `TOTAL_EPISODES` to control frequency
- Monitor epsilon decay to ensure exploration happens
- Always reset LSTM state at episode boundaries in Unity
- Use `verbose = true` in `DRQNInferenceAgent` for debugging

Happy training! 🎉
