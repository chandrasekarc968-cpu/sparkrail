"""
Digital Twin Simulation Module.
Interfaces with Eclipse SUMO for testing and RL training.
"""
from typing import Dict, Any, Tuple
import os
import sys

# Optional dependency logic for TraCI
try:
    import traci
    from sumolib import checkBinary
except ImportError:
    traci = None
    checkBinary = None

class SUMODigitalTwin:
    """Interface to Eclipse SUMO high-fidelity microscopic simulation."""
    
    def __init__(self, config: Dict[str, Any]) -> None:
        """
        Initialize the simulation environment.
        
        Args:
            config (Dict[str, Any]): Configuration for SUMO.
        """
        self.config_path: str = config.get("sumo_config_path", "sim/railway.sumocfg")
        self.gui: bool = config.get("use_gui", False)
        self.is_running: bool = False
        
        if traci is None:
            print("Warning: 'traci' and 'sumolib' not found. SUMO Digital Twin will run in dummy mode.")

    def reset(self) -> Dict[str, Any]:
        """
        Resets the simulation to the initial state and connects to TraCI server.
        
        Returns:
            Dict[str, Any]: The initial state of the railway network.
        """
        if traci is not None:
            if self.is_running:
                traci.close()
                
            sumo_binary = checkBinary('sumo-gui') if self.gui else checkBinary('sumo')
            traci.start([sumo_binary, "-c", self.config_path, "--start"])
            
        self.is_running = True
        return self._extract_state()

    def _extract_state(self) -> Dict[str, Any]:
        """
        Internal method to poll SUMO for the current physical network state.
        
        Returns:
            Dict[str, Any]: Dictionary representing train positions, speeds, and block occupancies.
        """
        state = {"vehicles": {}, "edges": {}}
        
        if traci is not None and self.is_running:
            # Poll vehicle states
            vehicle_ids = traci.vehicle.getIDList()
            for vid in vehicle_ids:
                state["vehicles"][vid] = {
                    "edge": traci.vehicle.getRoadID(vid),
                    "speed": traci.vehicle.getSpeed(vid),
                    "position": traci.vehicle.getLanePosition(vid)
                }
                
            # Poll edge/block states (e.g., induction loops/occupancy)
            edge_ids = traci.edge.getIDList()
            for eid in edge_ids:
                state["edges"][eid] = {
                    "vehicle_count": traci.edge.getLastStepVehicleNumber(eid)
                }
        else:
            # Dummy state for testing without SUMO installation
            state = {"vehicles": {"T1": {"edge": "E1", "speed": 10.0}}, "edges": {"E1": {"vehicle_count": 1}}}
            
        return state

    def step(self, action: Dict[str, Any]) -> Tuple[Dict[str, Any], float, bool, Dict[str, Any]]:
        """
        Applies a dispatching action to vehicles and steps the simulation forward.
        
        Args:
            action (Dict[str, Any]): The scheduling/dispatching action. e.g., {"T1": {"speed": 0.0}}
            
        Returns:
            Tuple: Next state, reward, done flag, and info dictionary.
        """
        if traci is not None and self.is_running and action:
            # Apply action: e.g., halt a train or adjust speed based on RL output
            for veh_id, commands in action.items():
                if "speed" in commands:
                    traci.vehicle.setSpeed(veh_id, commands["speed"])
        
        # Advance simulation by one step
        if traci is not None and self.is_running:
            traci.simulationStep()
            
        next_state = self._extract_state()
        
        # Simple dummy reward function for skeleton: maximize throughput
        reward = sum(v.get("speed", 0.0) for v in next_state["vehicles"].values())
        done = False
        info: Dict[str, Any] = {}
        
        return next_state, reward, done, info
        
    def close(self) -> None:
        """Terminates the SUMO simulation and closes TraCI."""
        if traci is not None and self.is_running:
            traci.close()
        self.is_running = False
