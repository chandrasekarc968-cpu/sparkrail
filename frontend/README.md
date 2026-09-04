# SparkRail Operations Control Room Frontend

Production-quality railway operations control-room interface for the **AI-Powered Automatic Block Planning System layered onto CRIS BDMS** (Indian Railways Problem Statement ID: 26027).

The interface connects to SparkRail's Three-Tier Optimization Engine to provide human-in-the-loop schedule review, multi-department shadow block visualization, statutory approval workflows, and emergency operational overrides.

---

## Key Features & Control-Room Ergonomics

- **Canonical Geometry Contract (`geometry_schema_version: "1.0.0"`)**:
  - Longitudinal corridor coordinates in meters ($x \in [-400\text{m}, +400\text{m}]$).
  - WebGL 3D corridor visualization with steel rails, ballast, OHE catenary masts, signal gantries, and stations.
  - Accessible 2D SVG schematic with WCAG AA compliance and tabular screen-reader fallback.
  - **Zero Geometry Invention**: In non-demo mode, track, train, and asset positions are strictly derived from the `/network/geometry` API.
- **Human-in-the-Loop Advisory Proposal Drawer**:
  - Slide-over governance workspace accessible directly from the Global Header, Block Planner, or 3D view.
  - **5 Operational Tabs**:
    1. *Recommended Blocks*: Individual block windows, track closure hours, and safety buffers.
    2. *Shadow Bundles*: Multi-department consolidated possessions with compatibility rationales.
    3. *Statutory Approval Hierarchy*: Multi-tier electronic sign-off tracking (`CTPC` $\to$ `Sr. DOM` $\to$ `Section Controller` $\to$ `Station Master`).
    4. *Train Regulation Plan*: Real-time delay assessments and station loop regulation plans.
    5. *Audit Trail*: Chronological, tamper-evident log of every approval, rejection, and operational override.
- **Operational Override Modal**:
  - Allows `Sr. DOM` or `Section Controller` to right-shift, expand, or cancel non-active possession windows.
  - Mandatory justification input (minimum 10 characters) enforcing statutory accountability.
- **Live Disruption & Safety Badging**:
  - Explicit badges for `ADVISORY MODE`, `SAFE TO EXECUTE`, `FROZEN WEEK 1`, and `ACTIVE POSSESSION`.
  - Prohibits displaying an advisory proposal as `GRANTED` until BDMS emits confirmation.

---

## Technology Stack

- **Core**: React 19, TypeScript, Vite
- **3D Engine**: Three.js, `@react-three/fiber`, `@react-three/drei`
- **Styling**: Tailwind CSS v4 with OKLCH Color Palette & Railway Control-Room Tokens
- **Icons**: Lucide React
- **Charts**: Recharts
- **Testing**: Vitest + React Testing Library + JSDOM (**49 tests across 11 suites**)
- **Linting & Types**: ESLint 9 (Flat Config), TypeScript 5.8+ (Strict, `erasableSyntaxOnly` compliant)

---

## Control-Room Design Standards

Adheres strictly to the Indian Railways Operating Control Room visual specification:
- **Canvas**: OKLCH neutral canvas (`oklch(0.985 0.005 240)`). No pure white (`#fff`) or pitch black (`#000`).
- **Signal Accents**: Signal Amber (`oklch(0.72 0.16 75)`) and Track Rust (`oklch(0.60 0.18 45)`).
- **Safety Tokens**: High-contrast operational green, caution amber, and emergency stop red.
- **Tabular Numerals**: Enforced `font-variant-numeric: tabular-nums` across all timestamps, chainage values, and KPI metrics.
- **Accessibility**: Touch targets $\ge 44\text{px}$, visible keyboard focus rings, and WCAG AA contrast compliance.

---

## Verification & Build Commands

```bash
# 1. Install dependencies
npm ci

# 2. Run lint check (0 errors, 0 warnings)
npm run lint

# 3. Run full Vitest suite (49 tests passing)
npm test -- --run

# 4. Build production static bundle
npm run build

# 5. Start development server
npm run dev
```
