# Knowledge Transfer: Warehouse DRQN Project

## Project Overview
This repository combines a Unity warehouse simulation with a deep reinforcement learning training pipeline for a Deep Recurrent Q-Network (DRQN) agent.

Main areas:
- `Assets/Scripts/` — Unity C# simulation, agent behavior, grid/environment management, statistics tracking, and time control.
- `Python-Training/` — PyTorch training code, replay buffer, DRQN architecture, ONNX export utilities, and integration tools for Unity.

## Unity Simulation (Assets/Scripts)

### `GridAgent.cs`
- Implements a Unity ML-Agents `Agent` subclass.
- Uses discrete actions: 0 = forward, 1 = backward, 2 = rotate right, 3 = rotate left.
- Tracks phases: `SeekCargo` and `DeliverCargo`.
- Observations:
  - Phase indicator
  - Normalized global target coordinates
  - Normalized agent coordinates
  - One-hot facing direction
  - Local vision around the agent using 5 relative offsets
- Reward design includes:
  - Sparse rewards for pickup and delivery
  - Step penalties, rotation cost, reverse move cost
  - Penalties for invalid moves, empty delivery zone visits, rack collisions, and collisions with other agents
  - Potential-based reward shaping (PBRS) based on Manhattan distance to target
- Handles cargo pickup, delivery transitions, and collision responses.
- Communicates with `WarehouseGridManager` and `WarehouseStatsManager`.

### `WarehouseGridManager.cs`
- Manages the grid environment and agent interactions.
- Defines grid size (`rows`, `cols`), delivery location, cargo spawn cells.
- Spawns cargo for each agent and keeps track of active cargo instances.
- Provides utility methods:
  - `GridToWorld()` converts grid coordinates to Unity world position.
  - `GetCargoLocation()`, `HasActiveCargo()`, `TryPickupCargo()`, `ClearCargoForAgent()`.
  - Agent occupancy checks and collision handling.
- On collision, applies a global collision penalty to all active agents and ends the episode.
- Chooses cargo spawn locations while avoiding delivery cells and occupied cells.

### `WarehouseStatsManager.cs`
- Collects team and per-agent statistics.
- Displays UI via TMPro and logs CSV summary files.
- Tracks:
  - total elapsed steps
  - team deliveries
  - total collisions
  - empty drop violations
  - per-agent deliveries, rack hits, step averages, best steps
- Writes detailed logs to:
  - `warehouse_stats.csv`
  - `warehouse_summary_metrics.csv`
- Supports snapshot logging intervals and flush control.

### `TimeController.cs`
- Controls Unity time scaling in the editor.
- Exposes a simple GUI slider to change `Time.timeScale` from 0.1x to 20x.
- Skips time scale adjustment if Unity is running in batch mode.

## Python Training Pipeline (Python-Training)

### `train.py`
- Main training and testing script for the DRQN.
- Uses Unity ML-Agents `UnityEnvironment` to interface with the compiled simulation.
- Supports modes:
  - `train` — fresh training
  - `resume` — continue from checkpoint
  - `test` — evaluation / inference only
- Hyperparameters are configured at top of file:
  - `GAMMA`, `LR`, `BATCH_SIZE`, `SEQ_LEN`, `TOTAL_EPISODES`, `ROLLOUT_STEPS`, `TRAIN_EVERY_STEPS`, `TARGET_UPDATE_FREQ`
  - epsilon schedule with exponential decay to a minimum exploration rate.
- Initializes PyTorch network, optimizer, and replay buffer.
- Loads checkpoints for `resume` and `test` modes.
- Creates a headless Unity environment and sets engine parameters (fast simulation with `time_scale=100.0`, uncapped frame rate).
- Implements training loop:
  - reset environment
  - step through episodes and rollout steps
  - build state/action/reward transitions per agent
  - sample from replay buffer every few decisions
  - optimize DRQN using Huber loss
  - update target network periodically
  - save checkpoints and export ONNX models
- In test mode, forces `epsilon = 0.0` and no training occurs.

### `drqn_model.py`
- Defines `DRQN` network architecture:
  - FC 14 → 64
  - LSTM 64 → 64
  - FC 64 → 4 Q-values
- `DRQNForONNX` wrapper prepares the model for ONNX export:
  - explicit LSTM hidden/cell state inputs and outputs
  - returns Q-values plus updated hidden and cell state
- `export_model_to_onnx()` exports the model to ONNX with:
  - opset version 14
  - dynamic axes on batch dimension
  - named inputs/outputs for Unity Barracuda integration

### `replay_buffer.py`
- Implements episodic replay storage for DRQN training.
- Stores transitions per agent and finishes episodes when `done` is reached.
- Supports sampling of sequences of fixed length (`SEQ_LEN`) across episodes.
- Returns batched tensors for state, action, reward, next state, and done.

### `export_checkpoint_to_onnx.py`
- Standalone utility for exporting existing `.pth` checkpoints to `.onnx`.
- Supports single checkpoint export and batch directory export.
- Loads model weights and uses the same `export_model_to_onnx()` function.

### Supporting Files
- `README.md` — project documentation for training, architecture, and integration.
- `REWARD_ANALYSIS.md` — in-depth reward design verification and issue analysis.

### `DRQNInferenceAgent.cs`
- Unity-side inference wrapper for ONNX model execution.
- Uses Barracuda `IWorker` to evaluate the model.
- Maintains LSTM hidden/cell state between frames.
- Provides methods:
  - `GetGreedyAction(observation)`
  - `GetExploratoryAction(observation, epsilon)`
  - `ResetEpisode()`
- Includes example usage class demonstrating integration into game logic.

## Key Design Concepts

### Observation Space
- 14-dimensional observation vector.
- Local perception uses a small set of relative offsets in front, behind, left, right, and two cells ahead.
- Tile encoding includes empty spaces, walls/out-of-bounds, cargo, delivery zone, racks, and other agents.

### Action Space
- 4 discrete actions:
  - 0 = forward
  - 1 = backward
  - 2 = rotate right
  - 3 = rotate left

### Reward Structure
- Sparse positive rewards for successful cargo pickup and delivery.
- Dense shaping rewards from PBRS to encourage progress to the current target.
- Penalties to discourage:
  - invalid moves
  - unnecessary rotations
  - backward motion
  - rack collisions
  - empty deliveries
  - agent collisions

### Multi-Agent Coordination
- The environment supports multiple agents in the same grid.
- `WarehouseGridManager` handles collisions and cargo assignment per agent.
- Collision handling applies negative reward to all agents and terminates the episode.

## How to Run

### Training
1. Ensure required Python packages are installed:
   - `torch`
   - `numpy`
   - `mlagents_envs`
2. Run:
   ```bash
   python Python-Training/train.py
   ```
3. Start Unity Editor or compiled build as configured in `train.py`.

### Testing / Inference
- Set `MODE = "test"` in `train.py`.
- Ensure `LOAD_MODEL_PATH` points to a valid `.pth` checkpoint.
- The script launches the Unity build and runs evaluations with greedy policy.

### ONNX Export
- Automatic export occurs during checkpoint saving in training mode.
- Use `export_checkpoint_to_onnx.py` for existing or legacy `.pth` checkpoints.

## Important Files to Know
- `Assets/Scripts/GridAgent.cs`
- `Assets/Scripts/WarehouseGridManager.cs`
- `Assets/Scripts/WarehouseStatsManager.cs`
- `Assets/Scripts/TimeController.cs`
- `Python-Training/train.py`
- `Python-Training/drqn_model.py`
- `Python-Training/replay_buffer.py`
- `Python-Training/DRQNInferenceAgent.cs`
- `Python-Training/export_checkpoint_to_onnx.py`
- `Python-Training/README.md`
- `Python-Training/REWARD_ANALYSIS.md`

## Notes and Recommendations
- Reward tuning is central: the repo already contains a reward analysis document that identifies asymmetries and penalty effects.
- The Unity inference agent expects ONNX inputs named `state`, `hidden_state`, and `cell_state`.
- The training script is currently configured for headless execution at `time_scale=100.0`.
- For faster iteration, inspect `WarehouseStatsManager` CSV logging and TensorBoard output from `runs/`.
- If you change observation layout, update both `GridAgent.CollectObservations()` and `DRQN` input size.

## Summary
This project is a hybrid Unity + PyTorch RL system for a grid-based warehouse task. The Unity side implements environment dynamics, agents, cargo handling, and metrics. The Python side trains a recurrent Q-network, stores episodic experiences, and exports inference-ready ONNX models for Unity Barracuda.

For the next handoff, focus on:
- how `GridAgent` transitions between seek and deliver phases,
- how `WarehouseGridManager` spawns cargo and resolves collisions,
- and how `train.py` interfaces with Unity and exports ONNX models.
