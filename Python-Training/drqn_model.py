import torch
import torch.nn as nn
import torch.nn.functional as F
import os

class DRQN(nn.Module):
    def __init__(self, input_size=14, hidden_size=64, num_actions=4):
        super(DRQN, self).__init__()
        self.input_size = input_size
        self.hidden_size = hidden_size
        self.num_actions = num_actions
        
        self.fc1 = nn.Linear(input_size, hidden_size)
        self.lstm = nn.LSTM(input_size=hidden_size, hidden_size=hidden_size, batch_first=True)
        self.fc2 = nn.Linear(hidden_size, num_actions)

    def forward(self, x, hidden_state=None):
        x = F.relu(self.fc1(x))
        out, hidden_state = self.lstm(x, hidden_state)
        
        # REMOVED the [:, -1, :] slice! 
        # Now outputs shape: (Batch, Sequence_Length, Num_Actions)
        q_values = self.fc2(out) 
        
        return q_values, hidden_state


class DRQNForONNX(nn.Module):
    """
    Wrapper for DRQN that exports cleanly to ONNX with explicit LSTM state handling.
    
    This is necessary because ONNX LSTM nodes require explicit h and c tensors as inputs/outputs,
    rather than the tuple format used in PyTorch training.
    
    Unity Barracuda Usage:
    - Input: state (1, 1, 14), h (1, 64), c (1, 64)
    - Output: q_values (1, 1, 4), h_out (1, 64), c_out (1, 64)
    
    In Unity C#:
        // Get current state and hidden/cell states from your agent
        Tensor state = new Tensor(..., data);    // shape [1, 1, 14]
        Tensor h = new Tensor(..., h_data);     // shape [1, 64]
        Tensor c = new Tensor(..., c_data);     // shape [1, 64]
        
        // Run inference
        var output = model.Execute(new Dictionary<string, Tensor> {
            { "state", state },
            { "hidden_state", h },
            { "cell_state", c }
        });
        
        // Get outputs
        Tensor qValues = output["q_values"];           // shape [1, 1, 4]
        Tensor h_new = output["hidden_state_out"];     // shape [1, 64]
        Tensor c_new = output["cell_state_out"];       // shape [1, 64]
        
        // Take the last timestep Q-values and select action
        float[] q_vals = qValues.AsFloats();
        int action = argmax(q_vals);
        
        // Store h_new and c_new for next timestep
    """
    
    def __init__(self, drqn_model):
        super(DRQNForONNX, self).__init__()
        self.drqn = drqn_model
        self.input_size = drqn_model.input_size
        self.hidden_size = drqn_model.hidden_size
        self.num_actions = drqn_model.num_actions

    def forward(self, state, hidden_state, cell_state):
        """
        Args:
            state: Input observation, shape (batch=1, seq_len=1, input_size=14)
            hidden_state: LSTM hidden state, shape (batch=1, hidden_size=64)
            cell_state: LSTM cell state, shape (batch=1, hidden_size=64)
        
        Returns:
            q_values: Q-values, shape (batch=1, seq_len=1, num_actions=4)
            hidden_state_out: Updated hidden state, shape (batch=1, hidden_size=64)
            cell_state_out: Updated cell state, shape (batch=1, hidden_size=64)
        """
        # Reshape states to match LSTM input format (batch, seq, hidden)
        h = hidden_state.unsqueeze(0)  # (1, hidden_size) → (1, 1, hidden_size)
        c = cell_state.unsqueeze(0)    # (1, hidden_size) → (1, 1, hidden_size)
        
        # Pass through the original DRQN (without slicing)
        q_values, (h_out, c_out) = self.drqn(state, (h, c))
        
        # Extract and reshape outputs
        h_out = h_out.squeeze(0)  # (1, 1, hidden_size) → (1, hidden_size)
        c_out = c_out.squeeze(0)  # (1, 1, hidden_size) → (1, hidden_size)
        
        return q_values, h_out, c_out


def export_model_to_onnx(model, output_dir="checkpoints", model_name="drqn_model"):
    """
    Export a trained DRQN model to ONNX format for use with Unity Barracuda.
    
    Args:
        model: The trained DRQN model
        output_dir: Directory to save the ONNX file
        model_name: Name prefix for the ONNX file (without extension)
    
    Returns:
        Path to the exported ONNX file
    """
    os.makedirs(output_dir, exist_ok=True)
    
    # Create wrapper that explicitly handles LSTM states
    onnx_model = DRQNForONNX(model).eval()
    
    # Detect model device (CPU or CUDA)
    model_device = next(model.parameters()).device
    
    # Create dummy inputs for ONNX export on the same device as the model
    # Batch size = 1, Sequence length = 1 (for single-step inference in Unity)
    dummy_state = torch.randn(1, 1, model.input_size, dtype=torch.float32, device=model_device)
    dummy_hidden = torch.randn(1, model.hidden_size, dtype=torch.float32, device=model_device)
    dummy_cell = torch.randn(1, model.hidden_size, dtype=torch.float32, device=model_device)
    
    onnx_path = os.path.join(output_dir, f"{model_name}.onnx")
    
    # Export to ONNX with explicit input/output names
    torch.onnx.export(
        onnx_model,
        (dummy_state, dummy_hidden, dummy_cell),
        onnx_path,
        input_names=['state', 'hidden_state', 'cell_state'],
        output_names=['q_values', 'hidden_state_out', 'cell_state_out'],
        dynamic_axes={
            'state': {0: 'batch'},
            'hidden_state': {0: 'batch'},
            'cell_state': {0: 'batch'},
            'q_values': {0: 'batch'},
            'hidden_state_out': {0: 'batch'},
            'cell_state_out': {0: 'batch'},
        },
        opset_version=14,  # Barracuda supports up to opset 14
        verbose=False,
        do_constant_folding=True
    )
    
    # CRITICAL: Restore model to training mode for continued training
    # CUDA RNNs require training mode for backward() to work
    model.train()
    
    print(f"✓ ONNX Model exported: {onnx_path}")
    return onnx_path
