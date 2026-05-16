# Pseudocode Based On `Assets\Scripts`

This pseudocode is based only on the source files currently present in:

- `Assets\Scripts\GridAgent.cs`
- `Assets\Scripts\WarehouseGridManager.cs`
- `Assets\Scripts\WarehouseStatsManager.cs`
- `Assets\Scripts\TimeController.cs`

No Unity scene, prefab, inspector, or training-runtime values are assumed here.

---

## Overall Warehouse Flow

```text
START Unity scene

WarehouseGridManager starts
    FOR each registered active agent:
        spawn a cargo assigned to that agent

Each GridAgent initializes
    enforce minimum reward penalties
    configure target line renderer
    register itself with stats manager if available
    register itself with grid manager if available

When an ML-Agents episode begins for an agent:
    set phase to SeekCargo
    set hasCargo to false

    IF agent is carrying cargo:
        destroy carried cargo
        clear carried cargo reference

    reset grid position to spawn position
    reset facing direction to spawn direction
    reset previous-position tracking

    ask grid manager to spawn new cargo for this agent
    update Unity transform position and rotation

During each agent decision:
    collect 14 observations
    receive one discrete action
    apply movement or rotation
    calculate rewards and penalties
    update cargo, delivery, collision, and stats state

END when Unity scene stops or ML-Agents closes the environment
```

---

## `GridAgent` Pseudocode

```text
DEFINE GridAgent as an ML-Agents Agent

CONSTANTS:
    gamma = 0.99
    shaping scale = 0.2
    invalid move penalty = 1.0
    minimum rack penalty = 15.0
    minimum empty dropzone penalty = 12.0
    minimum reverse move penalty = 0.20
    rotation base cost = 0.10

DEFINE agent phases:
    SeekCargo
    DeliverCargo

STORE:
    grid manager reference
    hold point reference
    currently carried cargo object
    spawn grid position
    spawn facing direction
    current grid position
    current facing direction
    whether agent has cargo
    stats manager reference
    agent id
    steps since pickup
    reward tuning values
    target line renderer
    previous grid position
    whether previous cell was a rack
```

### Initialization

```text
ON Initialize:
    enforce reward penalties to minimum allowed values

    get LineRenderer component
    IF line renderer exists:
        set start width
        set end width
        set line position count to 2

    IF stats manager exists:
        register this agent using agent id

ON Awake:
    run base agent awake logic

    IF grid manager exists:
        register this agent with grid manager
```

### Episode Reset

```text
ON Episode Begin:
    set current phase to SeekCargo
    set hasCargo to false

    IF carried cargo exists:
        destroy carried cargo
        clear carried cargo reference

    set current grid position to spawn grid position
    set facing direction to spawn facing direction
    set previous grid position to current grid position
    set previous cell was rack to false

    ask grid manager to spawn new cargo for this agent

    update physical world position from current grid position
    set transform rotation from facing direction
```

### Observations

```text
ON Collect Observations:
    observation 1:
        add 1 if current phase is DeliverCargo
        otherwise add 0

    determine current target:
        IF phase is SeekCargo:
            target is this agent's cargo location
        ELSE:
            target is delivery location

    observations 2 and 3:
        add target x divided by grid columns
        add target y divided by grid rows

    observations 4 and 5:
        add agent x divided by grid columns
        add agent y divided by grid rows

    observations 6 to 9:
        FOR each direction from 0 to 3:
            add 1 if facing direction equals that direction
            otherwise add 0

    observations 10 to 14:
        FOR each relative vision offset:
            rotate offset by current facing direction
            convert to global grid position

            IF global position is outside grid:
                tile state = wall/out of bounds
            ELSE IF another agent occupies that position:
                tile state = other agent
            ELSE IF that position contains this agent's active cargo and phase is SeekCargo:
                tile state = cargo
            ELSE IF that position is delivery location:
                tile state = delivery zone
            ELSE IF that position is a rack/cargo-spawn location:
                tile state = rack
            ELSE:
                tile state = empty

            add tile state

    total observations added = 14
```

### Action Handling

```text
ON Action Received:
    IF stats manager exists:
        increment global step count

    IF current phase is DeliverCargo:
        increment steps since pickup

    read discrete action

    determine current target:
        IF phase is SeekCargo:
            target is this agent's cargo location
        ELSE:
            target is delivery location

    calculate potential before action using negative Manhattan distance

    set step reward to 0
    set should calculate potential shaping to false
    set phase changed this step to false
    set episode ended to false

    IF action is rotate right or rotate left:
        rotate agent
        subtract rotation cost from reward
        do not calculate potential shaping

    ELSE IF action is move forward or move backward:
        get movement direction from facing direction
        determine whether movement is forward

        IF action is backward:
            invert movement direction
            subtract reverse move penalty

        calculate next grid position

        IF next position is outside grid:
            subtract invalid move penalty
            do not calculate potential shaping

        ELSE IF another agent occupies next position:
            IF stats manager exists:
                record collision

            ask grid manager to handle collision
            return from action handling

        ELSE:
            store previous grid position
            store whether previous cell was a rack

            move current grid position to next position
            update physical world position

            subtract base movement step penalty
            allow potential shaping

            IF current phase is SeekCargo:
                IF current position is delivery location:
                    subtract empty dropzone penalty
                    IF stats manager exists:
                        record empty drop

                IF current position is this agent's cargo location:
                    try visual pickup

                    IF pickup succeeds:
                        add pickup reward

                        IF movement was forward:
                            add forward pickup bonus
                        ELSE:
                            subtract reverse pickup penalty

                        set phase to DeliverCargo
                        reset steps since pickup
                        mark phase changed this step
                        disable potential shaping for this step

                ELSE IF current position is a rack/cargo-spawn location:
                    subtract rack penalty
                    IF stats manager exists:
                        record rack hit for this agent

            ELSE IF current phase is DeliverCargo:
                IF current position is delivery location AND agent has cargo:
                    add delivery success reward
                    disable potential shaping

                    IF stats manager exists:
                        record delivery with steps since pickup

                    visually drop cargo
                    ask grid manager to spawn new cargo for this agent
                    set phase to SeekCargo
                    reset steps since pickup
                    reset previous rack tracking

                ELSE IF movement was backward AND previous cell was a rack AND current cell is not a rack AND pickup was recent:
                    add rack-exit reverse bonus

                ELSE IF current position is a rack/cargo-spawn location:
                    subtract rack penalty
                    IF stats manager exists:
                        record rack hit for this agent

                ELSE IF current position is delivery location AND agent does not have cargo:
                    subtract empty dropzone penalty
                    IF stats manager exists:
                        record empty drop

    IF potential shaping is allowed AND phase did not change AND episode did not end:
        calculate potential after action
        shaping reward = gamma * next potential - previous potential
        add scaled shaping reward to step reward

    add step reward to ML-Agents reward

    IF episode ended:
        end episode
```

### GridAgent Helper Logic

```text
CalculatePotential(position, target):
    return negative Manhattan distance between position and target

RotateAgent(direction):
    update facing direction using wraparound from 0 to 3
    update transform rotation

GetForwardVector(direction):
    IF direction is 0:
        return north
    IF direction is 1:
        return east
    IF direction is 2:
        return south
    IF direction is 3:
        return west
    OTHERWISE:
        return zero vector

RotateVector(vector, direction):
    rotate a relative vision offset according to agent facing direction

OnValidate:
    enforce minimum penalties

EnforceMinimumPenalties:
    rack penalty cannot be below minimum rack penalty
    empty dropzone penalty cannot be below minimum empty dropzone penalty
    reverse move penalty cannot be below minimum reverse move penalty

IsRackLocation(grid position):
    return whether grid position exists in grid manager cargo spawn locations

UpdatePhysicalPosition:
    convert grid position to world position through grid manager
    assign transform position

HandleVisualPickup:
    ask grid manager to pick up cargo at current position

    IF cargo object is returned:
        set hasCargo to true
        parent cargo to hold point
        reset local cargo position and rotation
        return true

    return false

HandleVisualDrop:
    set hasCargo to false

    IF carried cargo exists:
        destroy it
        clear carried cargo reference

Update:
    IF application is running in batch mode:
        do nothing
    ELSE:
        update target line

UpdateTargetAndLine:
    IF target line does not exist:
        stop

    determine current target from phase
    set line start to agent position
    set line end to target world position
    use green line for delivery phase
    use red line for cargo-seeking phase
```

### Heuristic Controls

```text
ON Heuristic:
    default action is 4

    IF no keyboard is available:
        stop

    IF agent id is A0:
        W = forward
        S = backward
        D = rotate right
        A = rotate left

    ELSE IF agent id is A1:
        Up Arrow = forward
        Down Arrow = backward
        Right Arrow = rotate right
        Left Arrow = rotate left
```

---

## `WarehouseGridManager` Pseudocode

```text
DEFINE WarehouseGridManager

STORE:
    grid rows
    grid columns
    surface height
    delivery location
    list of active agents
    list of cargo spawn locations
    cargo prefab
    global collision penalty
    cargo location assigned to each agent
    active cargo object assigned to each agent
```

```text
ON Start:
    FOR each active agent:
        spawn new cargo for that agent

RegisterAgent(agent):
    IF agent exists AND is not already active:
        add agent to active agents list

GridToWorld(grid position):
    convert grid x and y to Unity world position
    use configured surface height
    return world position

GetCargoLocation(agent):
    IF cargo location exists for agent:
        return that location
    ELSE:
        return zero grid position

HasActiveCargo(agent):
    return whether active cargo object dictionary contains agent

SpawnNewCargoForAgent(agent):
    IF agent is missing OR cargo prefab is missing OR no cargo spawn locations exist:
        stop

    clear active cargo for this agent
    select cargo location for this agent
    store selected cargo location
    instantiate cargo prefab at selected world position
    store active cargo instance for this agent

TryPickupCargo(agent, agent position):
    IF no cargo location is assigned to this agent:
        return null

    IF agent position is not the assigned cargo location:
        return null

    IF active cargo instance does not exist or is null:
        return null

    remove active cargo instance from active-cargo dictionary
    return cargo object

ClearCargoForAgent(agent):
    clear active cargo object for this agent
    remove cargo location assignment for this agent

IsCellOccupiedByOtherAgent(target position, self):
    return whether GetAgentAtCell finds another agent

GetAgentAtCell(target position, self):
    FOR each active agent:
        IF agent exists AND is not self AND agent current grid position equals target position:
            return that agent

    return null

HandleAgentCollision(initiator, other agent):
    FOR each active agent:
        IF agent exists:
            apply negative global collision penalty

    FOR each active agent:
        IF agent exists:
            end that agent's episode
```

### Cargo Selection

```text
SelectCargoLocation(owner):
    create empty candidate list

    FOR each cargo spawn location:
        IF location equals delivery location:
            skip it

        IF any agent currently occupies location:
            skip it

        IF cargo is already assigned to another agent at location:
            skip it

        add location to candidates

    IF no candidates exist:
        use all cargo spawn locations as candidates

    choose random candidate
    return selected candidate

IsCellOccupiedByAnyAgent(target position):
    FOR each active agent:
        IF agent exists AND agent current grid position equals target position:
            return true

    return false

IsCargoAlreadyAssigned(target position, owner):
    FOR each stored cargo assignment:
        IF assigned agent is not owner
           AND assigned position equals target position
           AND assigned agent has an active cargo instance:
            return true

    return false

ClearActiveCargoForAgent(agent):
    IF active cargo object exists for agent:
        destroy active cargo object

    remove agent from active cargo object dictionary
```

---

## `WarehouseStatsManager` Pseudocode

```text
DEFINE WarehouseStatsManager

STORE UI settings:
    TextMeshPro stats text reference
    whether on-screen stats panel is shown
    panel position and size

STORE CSV settings:
    whether detailed CSV logging is enabled
    detailed CSV filename
    snapshot interval in steps
    CSV flush interval

STORE summary CSV settings:
    whether summary CSV logging is enabled
    summary CSV filename

STORE global metrics:
    total elapsed steps
    team deliveries
    total collisions
    empty drop violations

STORE per-agent metrics:
    agent id
    deliveries
    rack hits
    total steps taken after pickup
    best steps
    average steps
```

```text
ON Start:
    record session start time
    initialize detailed CSV log if enabled
    initialize summary CSV log if enabled
    update UI

RegisterAgent(agent, id):
    IF agent is not already registered:
        create stats entry for that agent

RecordDelivery(agent, steps since pickup):
    increment team deliveries
    increment this agent's deliveries
    add steps since pickup to this agent's total steps

    IF steps since pickup is better than current best:
        update best steps

    log delivery event
    update UI

RecordCollision:
    increment total collisions
    log collision event
    update UI

RecordRackHit(agent):
    increment this agent's rack hit count
    log rack hit event
    update UI

RecordEmptyDrop:
    increment empty drop violations
    log empty drop event
    update UI

IncrementGlobalStep:
    increment total elapsed steps

    IF step count is divisible by 10:
        update UI

    IF snapshot interval is enabled AND step count reaches snapshot interval:
        log step snapshot event
```

### CSV Logging

```text
InitializeCsvLog:
    IF detailed CSV logging is disabled OR writer already exists:
        stop

    build CSV file path in Unity persistent data path
    create directory if needed

    IF file does not exist OR file is empty:
        write detailed CSV header

InitializeSummaryCsvLog:
    IF summary CSV logging is disabled OR writer already exists:
        stop

    build summary CSV file path in Unity persistent data path
    create directory if needed

    IF file does not exist OR file is empty:
        write summary CSV header

LogEvent(event name, agent, steps since pickup):
    IF agent exists and has registered stats:
        use that agent's stats
    ELSE:
        use team-level stats

    calculate total rack hits
    calculate delivery rate
    calculate efficiency

    IF detailed CSV logging is enabled:
        initialize log if needed
        build detailed CSV row
        write row

    IF summary CSV logging is enabled:
        initialize summary log if needed
        build summary CSV row
        write row

WriteCsvRow(writer, row, rows since flush):
    IF writer is missing:
        stop

    write row
    increment rows since flush

    IF flush interval reached:
        flush writer
        reset rows since flush

ON Destroy:
    flush and close detailed CSV writer
    flush and close summary CSV writer
```

### Stats Calculations And UI

```text
GetTotalRackHits:
    sum rack hits from all registered agents

GetDeliveryRate:
    IF total elapsed steps is zero:
        return 0
    ELSE:
        return team deliveries divided by total elapsed steps

GetElapsedSeconds:
    return current realtime minus session start realtime

GetDeliveriesPerMinute:
    IF elapsed seconds is zero or less:
        return 0
    ELSE:
        return team deliveries times 60 divided by elapsed seconds

GetEfficiency(total rack hits):
    penalty weight =
        collisions times 50
        plus rack hits times 10
        plus empty drop violations times 5

    IF total elapsed steps plus penalty weight is zero or less:
        return 0

    score = team deliveries times 1000 divided by total elapsed steps plus penalty weight
    clamp score between 0 and 100
    return score

UpdateUI:
    build stats text

    IF TextMeshPro display exists:
        assign stats text to display

BuildStatsText:
    FOR each registered agent:
        add deliveries, average steps, and rack hits

    add team deliveries
    add collisions
    add total rack scrapes
    add deliveries per minute
    add delivery rate per step
    add efficiency score

    return text

ON GUI:
    IF stats panel is disabled OR application is batch mode:
        stop

    IF cached UI text is empty:
        build stats text

    draw metrics box
    draw cached stats text
    draw active CSV logging filename
```

---

## `TimeController` Pseudocode

```text
DEFINE TimeController

STORE:
    time scale value from 0.1 to 20

ON Update:
    IF application is running in batch mode:
        stop

    set Unity Time.timeScale to configured time scale

ON GUI:
    draw time scale controller box
    draw current speed label
    draw horizontal time-scale slider

    IF 1x button is clicked:
        set time scale to 1

    IF 10x button is clicked:
        set time scale to 10

    IF 20x button is clicked:
        set time scale to 20
```

---

## Verified From Code

```text
The agent observation vector contains 14 values.
The action handler uses actions 0, 1, 2, and 3.
The heuristic default action is 4, but OnActionReceived only handles 0 to 3.
Cargo is assigned per agent by WarehouseGridManager.
Successful delivery does not call EndEpisode in GridAgent; it spawns another cargo and returns to SeekCargo.
Agent collisions apply the global collision penalty to all active agents and end all active agents' episodes.
Stats can be shown on screen and written to CSV files in Application.persistentDataPath.
TimeController does not modify time scale in batch mode.
```

## Unknowns Not Assumed

```text
Exact inspector values in the Unity scene are not verified from these scripts alone.
Exact prefab assignments are not verified from these scripts alone.
Exact ML-Agents Behavior Parameters are not verified from these scripts alone.
The semantic meaning of each discrete action comes from GridAgent code only, not from a Behavior Parameters asset.
Scene object wiring between GridAgent, WarehouseGridManager, WarehouseStatsManager, cargo prefab, and hold point is not verified here.
```
