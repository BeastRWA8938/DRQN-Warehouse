## Pseudocode

START PROGRAM

SET mode to train, resume, or test
SET checkpoint path to load if resume/test is used

SET training hyperparameters:
    discount factor
    learning rate
    batch size
    sequence length
    total episodes
    rollout steps
    training frequency
    target network update frequency
    epsilon start, minimum, and decay

SELECT device:
    use CUDA if available
    otherwise use CPU

CREATE checkpoints folder if missing

CREATE policy DRQN network
CREATE target DRQN network
CREATE Adam optimizer
CREATE episodic replay buffer

SET starting episode to 1
SET current epsilon to epsilon start

IF mode is resume or test:
    IF checkpoint exists:
        LOAD checkpoint
        LOAD model weights into policy network

        IF mode is resume:
            LOAD optimizer state
            SET starting episode from checkpoint episode + 1
            SET epsilon from checkpoint

        IF mode is test:
            SET policy network to evaluation mode
            SET epsilon to 0
    ELSE:
        PRINT error and exit

COPY policy network weights into target network
SET target network to evaluation mode

IF mode is train or resume:
    CREATE TensorBoard writer

CREATE Unity engine configuration channel

IF mode is test:
    LAUNCH Unity environment from build path without no_graphics enabled
ELSE:
    LAUNCH Unity environment from build path with no_graphics enabled

SET Unity time scale to 100
RESET Unity environment
GET behavior name from Unity environment


DEFINE optimize_model:
    SAMPLE batch of episode sequences from replay buffer

    IF sample is not available:
        RETURN no loss

    MOVE sampled states, actions, rewards, next states, and dones to device

    RUN policy network on state sequence
    TAKE Q-values from final timestep
    SELECT Q-value matching final action in each sequence

    RUN target network on next-state sequence without gradients
    TAKE Q-values from final timestep
    FIND maximum next Q-value

    COMPUTE target Q-value:
        final reward + discount * max next Q * not done

    COMPUTE Smooth L1 loss between selected current Q and target Q

    ZERO optimizer gradients
    BACKPROPAGATE loss
    CLIP gradients
    UPDATE policy network

    RETURN loss value


DEFINE steps_to_dict:
    CONVERT Unity agent IDs into a dictionary:
        agent id -> index in step result


TRY:
    FOR each episode from starting episode to total episodes:
        RESET Unity environment
        FINISH all active replay-buffer episodes

        GET initial decision steps and terminal steps

        INITIALIZE per-agent dictionaries:
            current states
            hidden LSTM states
            rewards
            step counts
            terminal counts

        FOR each agent in current decision steps:
            STORE initial observation
            SET hidden state to none
            SET reward, steps, and terminal count to zero

        FOR each rollout step:
            CREATE empty action dictionary
            CREATE empty previous-state dictionary

            FOR each agent needing a decision:
                READ current observation
                STORE it as current state

                CONVERT observation to tensor shaped as one batch and one timestep

                RUN policy network using agent's previous hidden state
                RECEIVE Q-values and updated hidden state

                IF random number is less than epsilon:
                    CHOOSE random action from 0 to 3
                ELSE:
                    CHOOSE action with highest Q-value

                STORE updated hidden state
                STORE selected action
                STORE previous state

                SEND selected discrete action to Unity for that agent

            IF no actions were selected:
                STOP rollout loop

            STEP Unity environment

            GET next decision steps and terminal steps
            MAP next decision agent IDs to indexes
            MAP terminal agent IDs to indexes

            FOR each agent that acted:
                IF agent is in terminal steps:
                    GET next state, reward, and mark done true
                ELSE IF agent is in next decision steps:
                    GET next state, reward, and mark done false
                ELSE:
                    SKIP this agent

                ADD reward to agent's episode reward
                INCREMENT agent step count

                IF mode is train or resume:
                    PUSH transition into replay buffer:
                        previous state, action, reward, next state, done

                    INCREMENT decision counter

                    IF decision counter reaches training interval:
                        CALL optimize_model
                        IF loss exists:
                            ADD loss to episode loss total
                            INCREMENT training step count

                IF done:
                    INCREMENT terminal count
                    REMOVE agent state
                    REMOVE agent hidden state
                ELSE:
                    STORE next state for agent

            FOR each agent newly appearing in next decision steps:
                IF agent is not already tracked:
                    STORE observation
                    SET hidden state to none
                    INITIALIZE reward, step count, and terminal count if missing

            SET current decision steps to next decision steps

        FINISH all active replay-buffer episodes

        COMPUTE total reward across agents
        COMPUTE total steps across agents
        COMPUTE average loss if training occurred

        PRINT episode summary

        IF mode is train or resume:
            WRITE TensorBoard metrics:
                total reward
                total steps
                average loss
                epsilon
                per-agent reward
                per-agent terminal count

            DECAY epsilon but do not go below epsilon minimum

            IF episode matches target update frequency:
                COPY policy network weights into target network

            IF episode matches checkpoint interval:
                BUILD checkpoint name using:
                    episode
                    gamma
                    epsilon
                    replay-buffer frame count

                SAVE checkpoint containing:
                    episode
                    policy model weights
                    optimizer state
                    epsilon

                EXPORT policy network to ONNX

EXCEPT keyboard interrupt:
    PRINT interrupted message

FINALLY:
    CLOSE Unity environment
    CLOSE TensorBoard writer if it exists

END PROGRAM
Model Pseudocode

DEFINE DRQN model:
    INPUT observation size = 14
    HIDDEN size = 64
    ACTION count = 4

    LAYER 1:
        linear layer from 14 to 64

    RECURRENT LAYER:
        LSTM from 64 to 64

    OUTPUT LAYER:
        linear layer from 64 to 4

FORWARD PASS:
    APPLY first linear layer
    APPLY ReLU
    PASS result through LSTM using optional hidden state
    PASS every timestep output through final linear layer
    RETURN Q-values for all timesteps and updated hidden state
    
## Replay Buffer Pseudocode

CREATE episodic replay buffer:
    STORE completed episodes
    STORE currently active episode per agent
    TRACK total frames stored

WHEN pushing a transition:
    IF agent has no active episode:
        CREATE active episode for that agent

    ADD transition to that agent's active episode
    INCREMENT total frame count

    IF transition is done:
        FINISH that agent's episode

WHEN finishing an episode:
    REMOVE active episode for agent

    IF episode is empty:
        STOP

    ADD episode to memory

    WHILE memory exceeds capacity:
        REMOVE oldest episode
        SUBTRACT its length from total frame count

WHEN sampling:
    FILTER episodes that are at least sequence length long

    IF there are fewer valid episodes than batch size:
        RETURN none

    RANDOMLY select episodes

    FOR each selected episode:
        RANDOMLY choose a contiguous sequence
        SPLIT sequence into states, actions, rewards, next states, dones

    CONVERT batches to tensors
    RETURN tensor batch

## ONNX Export Pseudocode

LOAD checkpoint from path
CREATE DRQN model
LOAD checkpoint model weights into DRQN
SET model to evaluation mode

WRAP DRQN so ONNX receives:
    state
    hidden state
    cell state

WRAPPER FORWARD PASS:
    RESHAPE hidden and cell states for LSTM
    RUN DRQN
    RESHAPE output hidden and cell states
    RETURN Q-values, new hidden state, new cell state

CREATE dummy inputs:
    state shaped as batch 1, sequence 1, input size 14
    hidden state shaped as batch 1, hidden size 64
    cell state shaped as batch 1, hidden size 64

EXPORT model to ONNX with named inputs and outputs

IF batch export is requested:
    FIND all .pth files in checkpoint directory
    EXPORT each one
ELSE:
    EXPORT one checkpoint file