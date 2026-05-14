using UnityEngine;
using Unity.Barracuda;
using System.Collections.Generic;

/// <summary>
/// Minimal DRQN Inference Agent for Unity
/// 
/// Quick integration example - Use this as a starting point.
/// For production, integrate with your game's decision-making logic.
/// </summary>
public class DRQNInferenceAgent : MonoBehaviour
{
    [SerializeField] private NNModel onnxModelAsset;
    [SerializeField] private bool verbose = true;
    
    private IWorker worker;
    private float[] hiddenState;
    private float[] cellState;
    
    private const int INPUT_SIZE = 14;
    private const int HIDDEN_SIZE = 64;
    private const int NUM_ACTIONS = 4;
    
    void OnEnable()
    {
        if (onnxModelAsset == null)
        {
            Debug.LogError("DRQN ONNX model not assigned!");
            return;
        }
        
        var model = ModelLoader.Load(onnxModelAsset);
        worker = WorkerFactory.CreateWorker(WorkerFactory.Type.ComputePrecompiled, model);
        
        // Initialize LSTM states
        hiddenState = new float[HIDDEN_SIZE];
        cellState = new float[HIDDEN_SIZE];
        
        Log("DRQN Agent initialized");
    }
    
    /// <summary>
    /// Get the best action for the given observation
    /// </summary>
    public int GetGreedyAction(float[] observation)
    {
        return InferAction(observation);
    }
    
    /// <summary>
    /// Get action with epsilon-greedy exploration
    /// </summary>
    public int GetExploratoryAction(float[] observation, float epsilon)
    {
        if (Random.value < epsilon)
        {
            return Random.Range(0, NUM_ACTIONS);
        }
        return InferAction(observation);
    }
    
    /// <summary>
    /// Reset LSTM state (call at episode start)
    /// </summary>
    public void ResetEpisode()
    {
        System.Array.Clear(hiddenState, 0, hiddenState.Length);
        System.Array.Clear(cellState, 0, cellState.Length);
    }
    
    private int InferAction(float[] observation)
    {
        if (observation.Length != INPUT_SIZE)
        {
            Debug.LogError($"Invalid observation size: {observation.Length} (expected {INPUT_SIZE})");
            return 0;
        }
        
        // Create tensors
        using (var stateTensor = new Tensor(new Shape(1, 1, INPUT_SIZE), observation))
        using (var hiddenTensor = new Tensor(new Shape(1, HIDDEN_SIZE), hiddenState))
        using (var cellTensor = new Tensor(new Shape(1, HIDDEN_SIZE), cellState))
        {
            // Execute model
            worker.Execute(new Dictionary<string, Tensor>
            {
                { "state", stateTensor },
                { "hidden_state", hiddenTensor },
                { "cell_state", cellTensor }
            });
            
            // Read outputs
            var qValuesTensor = worker.PeekOutput("q_values");
            var hiddenOutTensor = worker.PeekOutput("hidden_state_out");
            var cellOutTensor = worker.PeekOutput("cell_state_out");
            
            float[] qValues = qValuesTensor.AsFloats();
            
            // Extract Q-values for this timestep
            float[] actionQValues = new float[NUM_ACTIONS];
            System.Array.Copy(qValues, qValues.Length - NUM_ACTIONS, actionQValues, 0, NUM_ACTIONS);
            
            // Update LSTM state
            hiddenState = hiddenOutTensor.AsFloats();
            cellState = cellOutTensor.AsFloats();
            
            // Find best action
            int bestAction = 0;
            float bestValue = actionQValues[0];
            for (int i = 1; i < NUM_ACTIONS; i++)
            {
                if (actionQValues[i] > bestValue)
                {
                    bestValue = actionQValues[i];
                    bestAction = i;
                }
            }
            
            Log($"Q-values: {string.Join(", ", System.Array.ConvertAll(actionQValues, x => x.ToString("F2")))} -> Action: {bestAction}");
            
            return bestAction;
        }
    }
    
    private void Log(string message)
    {
        if (verbose)
        {
            Debug.Log($"[DRQN] {message}");
        }
    }
    
    void OnDisable()
    {
        worker?.Dispose();
    }
}


/// <summary>
/// Example Usage Pattern
/// </summary>
public class ExampleUsage : MonoBehaviour
{
    public DRQNInferenceAgent agent;
    
    void Start()
    {
        // Episode starts - reset state
        agent.ResetEpisode();
    }
    
    void Update()
    {
        // Gather your 14 observations
        float[] observation = new float[14]
        {
            // Your state values here
            0f, 0f, 0f, 0f, 0f, 0f, 0f, 0f, 0f, 0f, 0f, 0f, 0f, 0f
        };
        
        // Get action (with some exploration)
        int action = agent.GetExploratoryAction(observation, epsilon: 0.05f);
        
        // Use action in your game logic
        ExecuteAction(action);
    }
    
    private void ExecuteAction(int action)
    {
        // Map action (0-3) to your game commands
        switch (action)
        {
            case 0: /* Forward */ break;
            case 1: /* Backward */ break;
            case 2: /* Left */ break;
            case 3: /* Right */ break;
        }
    }
}
