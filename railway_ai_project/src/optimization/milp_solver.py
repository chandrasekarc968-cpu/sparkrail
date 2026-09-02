"""
Mixed-Integer Linear Programming (MILP) Solver Module.
Uses pyscipopt to schedule train movements considering immovable maintenance blocks.
"""
from typing import List, Dict, Any, Tuple
from pyscipopt import Model, quicksum

class MaintenanceSchedulerMILP:
    """
    MILP Solver for railway scheduling with precedence and maintenance constraints.
    Combines classical Operations Research with capacity scheduling.
    """
    
    def __init__(self, weight_throughput: float = 1.0, weight_delay: float = 0.5, big_m: float = 1e6) -> None:
        """
        Initialize the MILP solver using SCIP.
        
        Args:
            weight_throughput (float): Weight for the throughput maximization objective.
            weight_delay (float): Penalty weight for delay minimization objective.
            big_m (float): Large constant used for disjunctive constraints.
        """
        self.model: Model = Model("Railway_Scheduling")
        self.weight_throughput = weight_throughput
        self.weight_delay = weight_delay
        self.big_m = big_m
        
        # Dictionaries to store SCIP variables
        self.arrival_times: Dict[Tuple[str, str], Any] = {}
        self.departure_times: Dict[Tuple[str, str], Any] = {}
        self.precedence_vars: Dict[Tuple[str, str, str], Any] = {}
        self.delay_vars: Dict[str, Any] = {}

    def build_model(self, trains: List[Dict[str, Any]], blocks: List[Dict[str, Any]], maintenance_blocks: List[Dict[str, Any]]) -> None:
        """
        Constructs the MILP model with decision variables, precedence, and capacity constraints.
        
        Args:
            trains: List of trains. Format: {'id': 'T1', 'route': ['B1', 'B2'], 'scheduled_start': 0.0, 'min_travel_times': {'B1': 5.0, ...}}
            blocks: List of track blocks (network sections). Format: {'id': 'B1'}
            maintenance_blocks: List of immovable track maintenance windows. Format: {'block_id': 'B1', 'start_time': 10.0, 'end_time': 20.0}
        """
        # 1. Define decision variables for schedule timings (continuous)
        for train in trains:
            t_id = train['id']
            # Total delay for the train
            self.delay_vars[t_id] = self.model.addVar(vtype="C", lb=0.0, name=f"delay_{t_id}")
            
            for block_id in train['route']:
                # Arrival and departure at each block in the train's route
                arr = self.model.addVar(vtype="C", lb=0.0, name=f"arr_{t_id}_{block_id}")
                dep = self.model.addVar(vtype="C", lb=0.0, name=f"dep_{t_id}_{block_id}")
                
                self.arrival_times[(t_id, block_id)] = arr
                self.departure_times[(t_id, block_id)] = dep
                
                # Physical constraint: Departure >= Arrival + min_travel_time
                min_travel = train['min_travel_times'].get(block_id, 1.0)
                self.model.addCons(dep >= arr + min_travel, name=f"travel_{t_id}_{block_id}")
                
            # Route continuity: Arrival at block i+1 >= Departure from block i
            route = train['route']
            for i in range(len(route) - 1):
                curr_b = route[i]
                next_b = route[i+1]
                self.model.addCons(
                    self.arrival_times[(t_id, next_b)] >= self.departure_times[(t_id, curr_b)],
                    name=f"continuity_{t_id}_{curr_b}_{next_b}"
                )
            
            # Start time constraint
            first_block = route[0]
            self.model.addCons(self.arrival_times[(t_id, first_block)] >= train['scheduled_start'], name=f"start_{t_id}")
            
            # Delay calculation constraint: delay >= actual_completion - scheduled_completion
            last_block = route[-1]
            scheduled_end = train.get('scheduled_end', train['scheduled_start'] + 10.0) # Dummy fallback
            self.model.addCons(
                self.delay_vars[t_id] >= self.departure_times[(t_id, last_block)] - scheduled_end,
                name=f"calc_delay_{t_id}"
            )

        # 2. Capacity Constraints (Precedence)
        # Prevent two trains from occupying the same block at the same time
        for block in blocks:
            b_id = block['id']
            trains_on_block = [t for t in trains if b_id in t['route']]
            
            for i in range(len(trains_on_block)):
                for j in range(i + 1, len(trains_on_block)):
                    t1, t2 = trains_on_block[i]['id'], trains_on_block[j]['id']
                    
                    # Binary variable: y = 1 if t1 precedes t2, 0 otherwise
                    y = self.model.addVar(vtype="B", name=f"prec_{t1}_{t2}_{b_id}")
                    self.precedence_vars[(t1, t2, b_id)] = y
                    
                    arr1, dep1 = self.arrival_times[(t1, b_id)], self.departure_times[(t1, b_id)]
                    arr2, dep2 = self.arrival_times[(t2, b_id)], self.departure_times[(t2, b_id)]
                    
                    # Disjunctive constraints utilizing Big-M
                    self.model.addCons(arr2 >= dep1 - self.big_m * (1 - y), name=f"cap_1_{t1}_{t2}_{b_id}")
                    self.model.addCons(arr1 >= dep2 - self.big_m * y, name=f"cap_2_{t1}_{t2}_{b_id}")

        # 3. Immovable Maintenance Block Constraints
        for mb in maintenance_blocks:
            b_id = mb['block_id']
            m_start = mb['start_time']
            m_end = mb['end_time']
            
            trains_on_block = [t for t in trains if b_id in t['route']]
            for t in trains_on_block:
                t_id = t['id']
                arr = self.arrival_times[(t_id, b_id)]
                dep = self.departure_times[(t_id, b_id)]
                
                # Binary variable: z = 1 if train runs before maintenance, 0 if after
                z = self.model.addVar(vtype="B", name=f"maint_prec_{t_id}_{b_id}_{m_start}")
                
                # If z == 1: train departs before maintenance starts
                self.model.addCons(dep <= m_start + self.big_m * (1 - z), name=f"maint_before_{t_id}_{b_id}")
                # If z == 0: train arrives after maintenance ends
                self.model.addCons(arr >= m_end - self.big_m * z, name=f"maint_after_{t_id}_{b_id}")

        # 4. Objective Function
        completion_sum = quicksum(self.departure_times[(t['id'], t['route'][-1])] for t in trains)
        delay_sum = quicksum(self.delay_vars[t['id']] for t in trains)
        
        self.model.setObjective(self.weight_throughput * completion_sum + self.weight_delay * delay_sum, "minimize")

    def solve(self) -> str:
        """
        Optimizes the constructed MILP model.
        
        Returns:
            str: The optimization status (e.g., 'optimal', 'infeasible').
        """
        self.model.optimize()
        status = self.model.getStatus()
        return status
