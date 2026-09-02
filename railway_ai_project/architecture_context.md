# AI-Powered Automatic Block Planning System Architecture
**Problem Statement ID:** 26027 | **Domain:** Indian Railways

## 1. Executive Summary & Problem Context
The operational scale of Indian Railways presents an unparalleled logistical challenge. With over 64,000 route kilometers, the network must balance the continuous movement of millions of tonnes of freight and passenger traffic with the critical necessity of routine infrastructure maintenance. Historically, scheduling track maintenance "blocks" (periods where a track is closed to traffic) has relied on manual, heuristic-driven decisions. This results in suboptimal utilization of heavy track machines, fragmented corridor availability, and compounded delays across the network. 

The **AI-Powered Automatic Block Planning System** directly addresses this challenge by replacing manual scheduling with algorithmic precision. This architecture guarantees maximized asset availability and minimal disruption to operations by intelligently forecasting, scheduling, and dynamically adjusting maintenance blocks using a hybrid of classical Operations Research (OR) and modern Artificial Intelligence (AI).

## 2. Data Integration Pipeline
To enable real-time, mathematically rigorous optimization, the system must ingest and harmonize siloed, heterogeneous data from legacy systems.

**Data Lakehouse Architecture:**
* **Apache Kafka:** Captures high-throughput, real-time streaming data from the Control Office Application (COA), including live train movements, dynamic ETAs, and signal changes via Change Data Capture (CDC).
* **Apache Spark Structured Streaming:** Serves as the processing engine to unify spatio-temporal streams, performing continuous dynamic spatial joins.
* **Delta Lake:** Provides ACID compliance over distributed Parquet files, ensuring concurrent reads and batch updates from legacy systems (like the Track Management System) do not corrupt data.
* **PostgreSQL / PostGIS:** Functions as the operational spatial datastore. PostGIS handles the rigorous geometric intersection logic required to map linear track referencing (chainage) to discrete operational block sections.

## 3. Hybrid Optimization Engine
The core of the scheduling logic is a hybrid engine that synergistically combines the mathematical guarantees of classical Operations Research with the tactical adaptability of modern AI. 

**Mixed-Integer Linear Programming (MILP) Formulation:**
The strategic baseline schedule (e.g., the 52-week Rolling Block Programme) is generated using an offline MILP solver. The MILP formulation guarantees absolute operational safety and global optimality over long planning horizons.
* **Objective Function:** Designed to maximize throughput and minimize cumulative train delay minutes.
* **Immovable Constraints:** Scheduled track maintenance blocks are treated as strict, immovable physical constraints. In the MILP model, these maintenance blocks function mathematically as **special "ghost trains"** with fixed, immutable schedules. When a "ghost train" occupies a block, that section of track is rendered completely unavailable to all other traffic for the specified maintenance duration, strictly enforcing safety clearances and shadow-block synchronization.

## 4. Graph Neural Network (GNN) State Encoder
For real-time operational adjustments, the system must possess acute state perception. This is achieved using a **Heterogeneous Graph Neural Network (GNN)** built on PyTorch Geometric.

* **Graph Representation:** The physical and operational railway network is encoded as a heterogeneous graph. Nodes represent diverse entities (e.g., trains, track sections, stations), while edges represent their relationships (e.g., train-occupies-track, track-connects-to-track).
* **Message Passing:** The GNN's forward pass performs continuous message passing along these edges, allowing each node to aggregate spatial and operational information from its neighborhood.
* **State Encoding:** The GNN transforms the raw, dynamic state of the network (train speeds, block occupancies) into a rich, fixed-size embedding vector for each node. This learned representation captures deep spatial contexts and traffic dependencies instantly.

## 5. Deep Reinforcement Learning (DRL) Dispatcher
While MILP excels at offline, macroscopic planning, it struggles with the state-space explosion required for sub-second, real-time rescheduling. When a sudden disruption invalidates the MILP schedule (e.g., an unexpected signal failure), the system falls back on a **Proximal Policy Optimization (PPO)** agent.

* **State Ingestion:** The DRL agent directly consumes the concatenated embedding vectors outputted by the GNN state encoder. For example, if two trains are approaching a conflict point, the agent analyzes their specific GNN embeddings.
* **Tactical Execution:** Operating with this rich state awareness, the PPO policy network outputs the optimal dispatching action from a discrete action space (e.g., holding a train, routing to a loop line, or shifting a maintenance window). This ensures the network recovers gracefully from disruptions while attempting to adhere to the overarching MILP strategic goals.

## 6. Digital Twin & Simulation Foundation
To train the DRL agent and validate the MILP schedules without risking live railway operations, the architecture relies on a rigorous simulation layer.

* **High-Fidelity Microscopic Simulation:** A digital twin of the targeted railway division is constructed using open-source traffic simulation tools like **Eclipse SUMO**.
* **Testbed & Training Ground:** This digital twin serves as the critical testbed for evaluating the shadow-blocking strategies of the MILP optimizer. Furthermore, it acts as the primary, real-time interactive training ground where the PPO RL agent explores the state space, learns the physics of train movements, and optimizes its reward function over millions of simulated episodes.
