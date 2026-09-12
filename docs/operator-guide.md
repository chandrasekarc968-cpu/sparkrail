# SparkRail 3D Digital-Twin Operator Guide

**Platform:** SparkRail AI Railway Corridor Maintenance Planning System  
**Audience:** CTPC, Sr. DOM, Section Controllers, Station Masters, and Maintenance Engineers  
**Mode of Operation:** Strictly Advisory Decision Support  

---

## 1. Role-Based Workflows

### 1.1 CTPC (Chief Traction Power Controller)
- **Primary Responsibility:** Ensure 25kV traction power safety and de-energization synchronization.
- **Workflow:**
  1. Open the 3D Digital-Twin and toggle the **OHE Isolation Impact** filter.
  2. Inspect highlighted orange segments to verify which elementary sections are de-energized.
  3. Verify that no electric locomotives (e.g. WAP-7 / WAG-9) are scheduled across the isolated elementary section during the possession window.
  4. In the **BDMS Proposals** drawer, review the CTPC traction safety clearance item before recording statutory approval.

### 1.2 Sr. DOM (Senior Divisional Operations Manager)
- **Primary Responsibility:** Maintain divisional punctuality index while delivering high-criticality maintenance.
- **Workflow:**
  1. Review the top KPI strip: Block Utilization (BUE), Shadow Block Ratio (SBR), and Punctuality Impact (PII).
  2. Inspect the **Active Conflicts** banner. If `🚫 APPROVAL BLOCKED` appears, examine the highlighted conflict marker to assess train delay impact.
  3. Verify that Class 1 premium passenger trains (Rajdhani, Vande Bharat) traverse with zero operational delay.
  4. Perform executive sanction in the BDMS Advisory Proposal drawer.

### 1.3 Section Controller
- **Primary Responsibility:** Real-time train regulation, headway monitoring, and loop holding.
- **Workflow:**
  1. Use the **Timeline Controller** to scrub forward across the next 4 to 8 hours.
  2. Check train speeds and positions along the corridor.
  3. Verify that freight consists are regulated at designated station loop lines (e.g. `NYN`, `BEP`) during heavy machine block execution.

### 1.4 Station Master
- **Primary Responsibility:** Local interlocking, point-machine position, and block instrument clearance.
- **Workflow:**
  1. Select your station node (e.g. `NODE_KCN` or `NODE_BEP`) on the 3D map or 2D schematic.
  2. Inspect the adjoining block limits and crossover turnouts.
  3. Confirm that no conflicting shunt movements are authorized into the possession envelope.

### 1.5 Maintenance Engineer (Civil, Electrical, S&T)
- **Primary Responsibility:** Efficient execution of track tamping, rail replacement, and signal overhauls.
- **Workflow:**
  1. Filter by Department (`Engineering`, `OHE`, or `S&T`).
  2. Inspect **Shadow Bundles** (green volumes `🔗`) to coordinate joint work within a single line block.
  3. Verify machine and crew assignments in the Planning Detail Inspector.

---

## 2. Navigating the 3D Corridor Digital-Twin

### 2.1 Camera Controls
- **Orbit / Rotate:** Click and drag the left mouse button.
- **Pan:** Click and drag the right mouse button (or Shift + Left click).
- **Zoom:** Scroll the mouse wheel.
- **Top-Down View:** Click the **Top-Down** button in viewport controls.
- **Side Elevation View:** Click the **Side Elevation** button in viewport controls.
- **Fit Network:** Click the **Fit Network** button to center the 80 km corridor.
- **Accessible 2D Schematic:** Click the **2D / 3D Toggle** button to switch to high-contrast SVG linear layout.

### 2.2 Keyboard Navigation Shortcuts
| Key | Action |
|:---|:---|
| <kbd>Space</kbd> | Play / Pause timeline simulation replay |
| <kbd>R</kbd> | Reset timeline to origin ($T+0.0\text{h}$) |
| <kbd>1</kbd> | Set playback speed to **1x** real-time |
| <kbd>2</kbd> | Set playback speed to **5x** simulation speed |
| <kbd>3</kbd> | Set playback speed to **15x** simulation speed |
| <kbd>4</kbd> | Set playback speed to **60x** fast-forward speed |

---

## 3. Interpreting Visual Semantics & Safety Indicators

SparkRail implements multi-modal encoding adhering to control-room ergonomics (color + icon + text + pattern):

| Visual Element | Visual Appearance | Meaning | Operator Action |
|:---|:---|:---|:---|
| **Neutral Track** | Slate Grey (`#64748b`) | Track available for normal traffic. | Standard operations. |
| **Planned Maintenance** | Amber (`#f59e0b`), wireframe | Possession scheduled by solver. | Review in BDMS drawer. |
| **Sanctioned Work** | Blue (`#3b82f6`), solid | Sanctioned by all 4 roles. | Staged for dispatch grant. |
| **Granted Possession** | Purple (`#8b5cf6`), 🔒 padlock | Formally granted under G&SR. | **IMMUTABLE**: Cannot move or drag. |
| **In-Progress Possession** | Red (`#ef4444`), hazard beacon | Work underway on active track. | **IMMUTABLE**: Protected track limit. |
| **Completed Work** | Muted Slate (`#6b7280`) | Maintenance finished, track handed back. | Speed restriction may apply. |
| **OHE Isolation** | Orange (`#f97316`), dashed | 25kV traction power de-energized. | No electric locos permitted. |
| **Signal Disconnection**| Magenta (`#c026d3`) | Signal bypass notice in effect. | Hand signalling protocol. |
| **Safety Conflict** | Flashing Red Diamond (`#ef4444`) | Severe spatiotemporal hazard. | **BLOCKS APPROVAL**: Resolve before sign-off. |

---

## 4. Planning Detail Inspector

Clicking any entity (Track, Station, Train, Possession, Conflict, or Asset) opens the side inspector panel:
- **Header:** Entity ID and immutable lock indicator if active.
- **Data Lineage & Provenance:** Source system (TMS, TDMS, SMMS, COA, RTIS), record ID, schema version (`1.0.0`), confidence percentage, and data age.
- **Technical Attributes:** Chainage limits, speed limits, duration, and assigned resources.
- **OHE & Signalling Constraints:** Affected elementary sections and disconnection notices.
- **AI Explainability:** Plain-English rationale for scheduling time, priority score, and protected trains.
