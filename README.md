# AI-Powered Railway Block Planning System

## Overview
This is the backend repository for the AI-Powered Railway Block Planning System.

## Architecture Modules
- **Data Pipeline**: Apache Kafka for streaming and PostgreSQL with PostGIS for spatial track topology.
- **Optimization**: Mixed-Integer Linear Programming (MILP) using `pyscipopt` for scheduling, considering immovable maintenance constraints.
- **AI & ML**: 
  - XGBoost for evaluating Task Criticality Indices.
  - PyTorch Geometric for Heterogeneous Graph Neural Network (GNN) state encoder.
- **Simulation**: High-fidelity digital twin interface (e.g. SUMO) as a testbed for the RL agent.

## Setup
Install requirements:
```bash
pip install -r requirements.txt
```
