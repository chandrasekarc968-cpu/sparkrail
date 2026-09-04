# SparkRail Mathematical Optimization Engine Specification

## 1. Overview & Architecture

SparkRail adopts a **Three-Tier Hierarchical Optimization Architecture** to balance mathematical rigor, computational tractability, and physical railway safety. Rather than solving a massive, monolithic Mixed-Integer Linear Program (MILP) that suffers from exponential combinatorial explosion on national corridors, the engine decomposes the problem into three synchronized stages:

```
+-------------------------------------------------------------------------------+
|                       TIER 1: DEMAND CLUSTERING                                |
|  - Multi-attribute Spatiotemporal Distance Metric                             |
|  - Compatibility Hypergraph & Safety Matrix                                   |
|  - Bron-Kerbosch Maximal Clique Extraction for Shadow Bundles                 |
+-------------------------------------------------------------------------------+
                                      |
                                      v
+-------------------------------------------------------------------------------+
|                   TIER 2: MACRO POSSESSION ALLOCATION                          |
|  - Integer Programming Formulation (OR-Tools CP-SAT)                          |
|  - Adaptive Large Neighborhood Search (ALNS) Heuristic Fallback               |
|  - Corridor-Wide Window Selection & Track Machine Scheduling                  |
+-------------------------------------------------------------------------------+
                                      |
                                      v
+-------------------------------------------------------------------------------+
|                 TIER 3: MICROSCOPIC DISPATCH VALIDATION                       |
|  - Continuous Train Trajectory & Minimum Headway Validation (0.1h / 6 mins)   |
|  - 25kV OHE Elementary-Section Electrical Traction Exclusion                  |
|  - Temporary Single Line (TSL) Meet-Pass Feasibility                          |
|  - Master-Subproblem Loop via Named Benders Feasibility Cuts                  |
+-------------------------------------------------------------------------------+
```

---

## 2. Mathematical Formulation

### 2.1 Indices & Sets
- $j \in \mathcal{J}$: Maintenance job requisitions.
- $k \in \mathcal{K}$: Track block sections.
- $t \in \mathcal{T} = \{0, 1, \dots, H\}$: Discrete planning time horizon (e.g., $H=24$ or $168$ hours).
- $r \in \mathcal{R}$: Track maintenance machines (BCM, CSM, Tamping, Wiring train) and crew sets.
- $m \in \mathcal{M}$: Moving train services (Class 1 Premium, Express, Freight).
- $b \in \mathcal{B}$: Candidate shadow possession bundles extracted from Tier 1.

### 2.2 Decision Variables
- $x_{j,t} \in \{0, 1\}$: Binary variable equal to 1 if maintenance job $j$ initiates execution at hour $t$; 0 otherwise.
- $u_j \in \{0, 1\}$: Binary variable equal to 1 if job $j$ is sanctioned in the current planning horizon.
- $y_{k,t} \in \{0, 1\}$: Binary variable equal to 1 if block section $k$ is closed to commercial traffic at hour $t$.
- $v_{k,t} \in \{0, 1\}$: Binary variable indicating that a fresh possession window commences on block $k$ at hour $t$.
- $s_{b} \in \{0, 1\}$: Binary variable equal to 1 if candidate shadow bundle $b$ is selected.
- $d_m \ge 0$: Continuous accumulated delay in hours incurred by train $m$.

---

### 2.3 Objective Function

Maximize net infrastructure availability and safety risk reduction while minimizing commercial train delay:

$$\max \mathcal{Z} = \sum_{j \in \mathcal{J}} \text{TCI}(j) \cdot u_j - \alpha \sum_{k \in \mathcal{K}} \sum_{t \in \mathcal{T}} y_{k,t} - \beta \sum_{m \in \mathcal{M}} w_m \cdot d_m + \gamma \sum_{b \in \mathcal{B}} \text{TCI}_{\text{bonus}}(b) \cdot s_b$$

Where:
- $\text{TCI}(j) \in [0, 100]$: Task Criticality Index of job $j$.
- $\alpha$: Block closure duration penalty (encourages compact possessions).
- $\beta$: Downstream train punctuality penalty.
- $w_m$: Train priority weight ($w_{\text{PREMIUM}} = 100$, $w_{\text{EXPRESS}} = 20$, $w_{\text{FREIGHT}} = 1$).
- $\gamma$: Shadow bundling efficiency incentive.

---

### 2.4 Hard Operational & Safety Constraints

1. **Job Execution Continuity:**
   If job $j$ is scheduled, it must run uninterrupted for its required duration $D_j$:
   $$\sum_{t' = t}^{t + D_j - 1} y_{k(j), t'} \ge D_j \cdot x_{j,t} \quad \forall j \in \mathcal{J}, \forall t \in \mathcal{T}$$

2. **Block Occupancy & Mutual Exclusion:**
   A block section can only support mutually compatible jobs concurrently:
   $$x_{j_1, t} + x_{j_2, t} \le 1 \quad \forall (j_1, j_2) \in \text{IncompatiblePairs}$$

3. **Track Machine Non-Overlapping:**
   A specialized machine $r$ cannot occupy two distinct locations simultaneously:
   $$\sum_{j \in \mathcal{J}_r} \sum_{\tau = t - D_j + 1}^{t} x_{j, \tau} \le C_r \quad \forall r \in \mathcal{R}, \forall t \in \mathcal{T}$$

4. **Frozen Week 1 Immutability:**
   Pre-existing sanctioned possessions within Week 1 are locked:
   $$x_{j, t_{\text{sanctioned}}} = 1 \quad \forall j \in \mathcal{J}_{\text{Frozen}}$$

5. **Active Granted Possession Absolute Lock:**
   Active `GRANTED` and `IN_PROGRESS` work cannot be moved, right-shifted, or shortened:
   $$u_j = 1, \quad x_{j, t_{\text{granted}}} = 1 \quad \forall j \in \mathcal{J}_{\text{ActiveGranted}}$$

6. **Class 1 Premium Train Protection:**
   Class 1 trains (Rajdhani, Vande Bharat, Shatabdi) are guaranteed strict headway protection:
   $$d_m \le d_{\max}(m) = 0.0 \quad \forall m \in \mathcal{M}_{\text{PREMIUM}}$$

---

## 3. Tier Breakdown

### 3.1 Tier 1: Spatiotemporal Demand Clustering (`src/optimization/clustering.py`)
- Evaluates multi-attribute distance metric:
  $$\Delta(j_1, j_2) = \sqrt{\left(\frac{\Delta \text{km}}{10.0}\right)^2 + \left(\frac{\Delta \text{hrs}}{4.0}\right)^2}$$
- Evaluates inter-departmental safety matrix (e.g., Civil tamping under de-energized OHE is compatible; live S&T electronic circuit testing with 25kV de-energization is strictly prohibited).
- Constructs the compatibility graph and applies **Bron-Kerbosch maximal clique extraction** with pivoting to extract maximal bundled shadow possession candidates.

### 3.2 Tier 2: Macro Possession Window Allocator (`src/optimization/macro_allocator.py`)
- Executes OR-Tools CP-SAT integer programming where available.
- Features high-performance **Adaptive Large Neighborhood Search (ALNS)** deterministic heuristic fallback:
  - *Worst-Delay Removal:* Destroys possessions generating excessive passenger train delays.
  - *Corridor Sweep Removal:* Clears spatial corridors around high-priority freight paths.
  - *Regret-3 Reinsertion:* Reinserts high-TCI candidate bundles into lowest-delay corridor slots.
  - *Machine Relocation Repair:* Smooths transit time between geographically separated work zones.

### 3.3 Tier 3: Microscopic Dispatch Validator (`src/optimization/microscopic_validator.py`)
- Performs continuous-time simulation of commercial train trajectories through physical block sections.
- Enforces strict automatic block headways (minimum 6 minutes / 0.1 hours).
- Enforces **25kV OHE Elementary-Section Isolation**: Prohibits electric locomotives from entering de-energized electrical sections during catenary maintenance.
- Issues named **Benders Cuts** (`ELECTRICAL_ISOLATION`, `HEADWAY_VIOLATION`, `PREMIUM_DELAY_EXCEEDED`) back to the macro solver when microscopic conflicts occur.

---

## 4. Live Disruption Rescheduling (`src/optimization/disruption_engine.py`)

When field disruptions occur (e.g. freight derailment, locomotive failure, weather restriction, or late possession clearance confirmation):
1. **Corridor Bounding:** Confines re-optimization to an affected radius (default: 25 km).
2. **Decision Freezing:** All decisions outside the affected corridor remain strictly frozen.
3. **Hard Immutability:** Active `GRANTED` and `IN_PROGRESS` track possessions are treated as immovable physical boundary conditions.
4. **Right-Shifting:** Sanctioned but unstarted work is shifted rightward to preserve corridor safety.
5. **Warm-Starting:** Initializes from the previous valid schedule, converging in **< 1.0 second** on benchmark corridors (well within the statutory 90-second operational threshold).
