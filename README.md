# SparkRail AI Block Planning System

An AI-Powered Automatic Block Planning System designed to maximize asset availability for train operations, specifically solving Indian Railways Problem Statement ID: 26027.

## Architecture

The system utilizes a hybrid approach, combining modern Machine Learning (for job criticality scoring) with rigorous Operations Research (MILP optimization) to build shadow block schedules. 

```mermaid
graph TD
    A[Data Ingestion (Local/Kafka/PostGIS)] --> B[TCI Scorer]
    B --> C[MILP Optimizer (PySCIPOpt)]
    C --> D[Local Simulator / Evaluator]
    D --> E[KPI Report]
    
    API[FastAPI Server] -.-> A
```

## Features
- **Task Criticality Index (TCI)**: Prioritizes jobs based on Safety, Delay Impact, Degradation Velocity, and Overdue Penalty.
- **Shadow Block Optimizer (MILP)**: PySCIPOpt-based scheduler that optimally stacks compatible department jobs (Engineering, OHE, S&T) into the same time window, avoiding premium train disruptions.
- **Rolling Horizon**: Week 1 jobs are frozen; future weeks are fluid.
- **Deterministic Heuristic Fallback**: Runs natively in local environments without needing C++ SCIP dependencies.
- **Local Simulation**: Evaluates KPIs (BUE, SBR, PII) directly against a strict deterministic First-Come-First-Serve baseline without needing SUMO.

*Note: Experimental Deep Reinforcement Learning (DRL) and Graph Neural Network (GNN) modules are not part of this core production MVP and are isolated for future experimental use.*

## Setup & Installation

```bash
# Clone the repository
git clone https://github.com/chandrasekarc968-cpu/sparkrail.git
cd sparkrail

# Install dependencies
python -m pip install -r requirements.txt

# Create .env config
cp .env.example .env
```

## CLI Usage

The repository can be operated end-to-end via the CLI.

```bash
# 1. Run full demo
python -m src.cli demo

# Or run steps manually:
python -m src.cli generate-data
python -m src.cli score
python -m src.cli optimize
python -m src.cli evaluate
```

## API Usage

The system exposes a FastAPI layer for web/microservice integration.

```bash
uvicorn src.api.main:app --reload
```
Endpoints:
- `POST /data/generate`
- `POST /score`
- `POST /optimize`
- `POST /evaluate`

## Testing

Run the full pytest suite (no internet/Kafka/SCIP required):
```bash
pytest -q
```

## Configuration
Edit `config/settings.yaml` to modify MILP time limits, TCI weights, or external database URLs.
