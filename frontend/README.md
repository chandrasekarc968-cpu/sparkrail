# SparkRail AI Block Planning System - Frontend

Production-quality railway operations control-room interface for the **AI-Powered Automatic Block Planning System** on Indian Railways (Problem Statement ID: 26027).

The system replaces manual, heuristic-driven block coordination with mathematical scheduling powered by Mixed-Integer Linear Programming (MILP), Task Criticality Index (TCI), and multi-department shadow-block synchronization.

---

## Technology Stack

- **Core**: React 19, TypeScript, Vite
- **3D Engine**: Three.js, `@react-three/fiber`, `@react-three/drei`
- **Styling**: Tailwind CSS v4 with OKLCH Color Palette & Railway Control-Room Tokens
- **Icons**: Lucide React
- **Charts**: Recharts
- **Testing**: Vitest + React Testing Library + JSDOM (29 tests across 8 suites)
- **Linting & Types**: ESLint 9 (Flat Config), TypeScript 5.8+ (Strict, `erasableSyntaxOnly` compliant)

---

## Control-Room Visual Design System

The interface adheres strictly to an Indian Railways control-room standard rather than a generic SaaS template:
- **Theme**: Light theme default with OKLCH neutral canvas (`oklch(0.985 0.005 240)`). Never pure white (`#fff`) or pure black (`#000`).
- **Accents**: Restrained Signal Amber (`oklch(0.72 0.16 75)`) and Rust Orange (`oklch(0.60 0.18 45)`).
- **Operational Safety Tokens**: Clear safety red (`--color-op-red`), warning amber (`--color-op-amber`), operational green (`--color-op-green`), and information blue (`--color-op-blue`).
- **Typography & Numerals**: Inter with enforced `font-variant-numeric: tabular-nums` across metrics, tables, timelines, and timestamps.
- **Strict Ergonomics**: Minimum 44px touch target on interactive elements, visible focus indicators, and accessible `prefers-reduced-motion` overrides. No generic SaaS glassmorphism, decorative 3D illustrations, or em dashes in UI copy.

---

## 8 Primary Operational Views

1. **Operations Overview (`/overview`)**:
   - Dominant division operations summary area with real-time health indicator.
   - Compact 8-metric KPI rail: Active Blocks, Scheduled Tasks, High-TCI Critical Queue, Train Delay Impact (PII), Shadow Block Ratio (SBR), Block Utilization Efficiency (BUE), Mean Time to Grant (MTTG), and Critical Asset Alerts.
   - 24-hour horizontal today's corridor occupancy strip.
   - Ranked Task Criticality Index queue (Top 5 high-TCI jobs).
   - Block section status (B1 to B8) with speed restrictions.
   - Department workload distribution (Engineering, S&T, OHE).
   - "Run Optimization" (MILP solver trigger) and "Review Conflicts" modal actions.

2. **3D Railway Corridor & Allocation Control Room (`/3d`)**:
   - WebGL-powered 3D corridor visualization representing Prayagraj Division (SFG to MZP, 80 km).
   - High-fidelity physical assets: 3D steel rails, ballast foundation, OHE catenary masts, signal gantries, and stations.
   - Multi-attribute operational state encoding: Available, Active Maintenance, Planned Possession, Frozen Week 1, Fixed Block, Multi-Department Shadow Block, High-Risk Asset, and Active Conflict.
   - Dynamic simulation timeline with play/pause, scrub, 0.5x–5x speed, and horizon presets (24h, 48h, 7d, 28d).
   - Multi-angle camera controls: Fit to Network, Reset Angle, Overhead Top-Down, and Side Elevation.
   - Accessible 2D SVG Schematic fallback with tabular operational status for low-power or non-WebGL environments.
   - Planning Detail Inspector with job TCI component breakdown, AI explainability, and train protection notes.

3. **Block Planner (`/planner`)**:
   - 3-pane scheduling workspace: Left filter rail, Center horizontal 24h/48h Gantt timeline, Right task inspector drawer.
   - Interactive timeline displaying track blocks B1 to B8, maintenance possessions, train movements, fixed/immovable blocks (`FB1`, `FB2`), and multi-department shadow blocks.
   - Distinct **Frozen Week 1** visual treatment with locked boundary badges and diagonal striping.
   - Conflict markers highlighting train delay cascades.
   - Comprehensive task inspector detailing mathematical TCI component breakdown (Safety, Delay, Degradation, Overdue) and solver rationale.

3. **Maintenance Jobs (`/jobs`)**:
   - High-density tabular register supporting search, column sorting, pagination, and column visibility customization.
   - Accessible TCI severity badges with numeric values and screen-reader text labels.
   - Real CSV export with standard browser download.
   - Slide-over detail inspection drawer for deep dive into equipment allocations and safety clearances.
   - Bulk selection UI with status counter.

4. **Live Operations (`/live`)**:
   - Real-time schematic track diagram spanning 80 route kilometers (Station A Ghaziabad to Station I Phaphund).
   - Dynamic train tracking (`T1` Rajdhani, `T2` Shatabdi, `T3` Vande Bharat, `T4`-`T10` Freight/Express).
   - Active block possession boundaries with safety exclusion zones.
   - Simulation replay toolbar: Play, Pause, Reset to 00:00, Speed multipliers (1x, 2x, 5x), and Scrubbing.
   - Premium train proximity warnings and live machine/crew telemetry.

5. **Asset Health (`/assets`)**:
   - Physical flaw surveillance (Ultrasonic Flaw Detection USFD, Track Recording Car TRC indices).
   - Clear visual distinction between **Observed Condition (TMS Sensors)** and **Predicted Failure (AI Degradation Model)**.
   - Linear asset risk heatmap across sections B1 to B8.
   - Degradation velocity ranking (mm/MGT) and direct drilldown to mitigating maintenance jobs.

6. **Reports (`/reports`)**:
   - Comparative evaluation of AI-Optimized schedule against manual baseline operations.
   - Side-by-side data table across 9 core performance dimensions: BUE (134.5% vs 100%), SBR (17.65%), PII Delays (4.0h vs 42.0h), Closure Hours (29.0h vs 39.0h), and Solver Runtime (0.25s).
   - Visual charts (Recharts) and real CSV / JSON report downloads.

7. **Settings (`/settings`)**:
   - Backend FastAPI Base URL configuration with live test ping.
   - Demo mode toggle with instant reactive state persistence across all components.
   - Active railway division selector (Prayagraj, Delhi, Howrah, Secunderabad).
   - TCI weight simulator validating sum-to-1.0 constraints.
   - Feature flags for experimental GNN State Encoder (PyTorch Geometric) and DRL Dispatcher (SUMO digital twin).

---

## Getting Started

### Prerequisites

- Node.js 18+
- npm 9+

### Installation

```bash
cd frontend
npm install
```

### Environment Configuration

Copy the example environment file:
```bash
cp .env.example .env
```

Available variables:
- `VITE_API_BASE_URL`: URL of the FastAPI backend (Default: `http://localhost:8000`).
- `VITE_DEMO_MODE`: Set to `true` (default) to run on deterministic local simulation data, or `false` to make live HTTP requests.

### Development Server

```bash
npm run dev
```
Starts the Vite development server with HMR at `http://localhost:5173`.

### Running Tests

```bash
npm test -- --run
```
Runs the Vitest suite covering API client, demo mode, TCI badges, KPI calculations, planner timeline, job filtering, and accessibility landmarks.

### Linting & Type Checking

```bash
npm run lint
npm run build
```
Validates ESLint rules, TypeScript strict types, and generates production build bundles in `dist/`.
