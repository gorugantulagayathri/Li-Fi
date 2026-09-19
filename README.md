# Dynamic Li-Fi Beam Scheduling for High-Density Indoor Environments
## Software-Only Li-Fi Digital Twin Prototype (Photonics Hackathon Project)

> **Important Technical Disclaimer:**
> *This software is a digital-twin simulation prototype designed for modeling and demonstration. The SLM (Spatial Light Modulator) component is a simplified computational/phase-gradient model inspired by optical beam steering and does not control physical hardware.*

---

## 1. Project Overview
This project presents a software-only **Li-Fi Digital Twin** that simulates optical wireless communication in a crowded indoor environment with ceiling-mounted Access Points (APs), mobile users, and physical obstacles (bookshelves, partitions, desks).

Li-Fi offers high-bandwidth, interference-free optical wireless communications using light waves (visible/infrared). However, because Li-Fi relies strictly on optical Line-of-Sight (LOS), physical obstacles or moving humans cause link blockages, leading to sudden outages. This prototype demonstrates dynamic beam scheduling, predictive blockage detection, and SLM-inspired phase-gradient beam steering to maintain continuous high-speed optical connectivity.

---

## 2. Problem Statement
In crowded indoor spaces (e.g., open offices, lecture halls, hospital wards):
- Users move dynamically, crossing optical paths.
- Physical objects and human blockers interrupt optical line-of-sight.
- Static AP beam assignment leads to frequent link dropouts and uneven network load.

---

## 3. Proposed Solution
Our digital twin implements:
1. **Geometric Line-of-Sight Blockage Engine**: Real-time 2D line segment / rectangle intersection check to detect optical path obstruction.
2. **Predictive Blockage Warning**: Forward trajectory projection (1.5s lookahead) to flag impending blockages before connection failure.
3. **Multi-Objective Dynamic Scheduler**: Evaluates candidate AP beams based on link quality, distance, user priority, AP load, fairness, and handover cost.
4. **SLM-Inspired Phase Mask Model**: Generates 2D phase gradient masks $\Phi(x,y) = \text{mod}\left(\frac{2\pi}{\lambda}(x \sin\theta_x + y \sin\theta_y), 2\pi\right)$ and computes 2D FFT far-field diffraction spot steering.
5. **Interactive Research Dashboard**: Real-time Plotly top-down floorplan, live KPI metrics, explainable decision cards, and scenario benchmarks built with Streamlit.

---

## 4. System Architecture
```
                                USER MOBILITY
                                     │
                             POSITION UPDATE (dt)
                                     │
                          OPTICAL LINK CHANNEL ENGINE
                   (Distance, FOV Angle, Lambertian Gain)
                                     │
                          BLOCKAGE DETECTION ENGINE
                    (Geometric Line-Rectangle Intersection)
                                     │
                             BEAM SCHEDULER
                 (Static / Reactive / Dynamic Multi-Objective)
                                     │
                       SLM BEAM STEERING MODEL
               (Phase Mask Grid -> 2D FFT Far-Field Spot)
                                     │
                         STREAMLIT DIGITAL TWIN UI
                   (Plotly Floorplan, KPIs, Event Log)
```

---

## 5. Module Descriptions
- **`app.py`**: Streamlit dashboard orchestration, Plotly floorplan layout, metric widgets, and 5 interactive tabs.
- **`simulation.py`**: Main simulation clock, state updates, step loop, predictive blockage lookahead, and event logging.
- **`environment.py`**: `AccessPoint`, `Obstacle`, and `Environment` management classes.
- **`users.py`**: `User` dataclass, mobility engines (Random Walk, Directed, Scenario paths), and movement history trails.
- **`optics.py`**: Optical Lambertian channel model, Photodiode FOV, distance attenuation, and geometric LOS blockage detector.
- **`scheduler.py`**: Beam assignment algorithms (Static, Reactive, and Dynamic multi-objective scoring with transparent explainability).
- **`slm.py`**: Spatial Light Modulator computational phase-gradient calculator and 2D FFT far-field intensity visualization.
- **`metrics.py`**: Real-time KPI engine (Connectivity ratio, Jain's Fairness Index, Outage duration, Throughput, Latency).
- **`scenarios.py`**: Predefined demonstration scenarios (*Free Movement*, *Walking Through Beam*, *High Density*, *Multiple Blockages*).
- **`config.py`**: System default parameters, room dimensions, optical channel constants, and default scheduler weights.
- **`utils.py`**: 2D line segment / rectangle intersection geometry algorithms and vector math helpers.

---

## 6. Optical Model Assumptions
- Ceiling-mounted APs point vertically downward ($z = 3.0\text{m}$).
- User optical photodiodes point vertically upward ($z = 1.0\text{m}$).
- Lambertian LED emission semi-angle $\phi_{1/2} = 60^\circ$ ($m = 1.0$).
- Photodiode Field of View (FOV) $\Psi_c = 60^\circ$.
- If LOS is geometrically blocked by an obstacle, link quality drops to $0.0$.

---

## 7. Blockage Detection Method
For every AP-User link:
1. Draw line segment $P_1(x_{ap}, y_{ap}) \to P_2(x_{user}, y_{user})$.
2. Test intersection with each rectangular obstacle bounding box $(x, y, w, h)$.
3. If line intersects rectangle boundary or endpoint lies inside, $\text{LOS} = \text{BLOCKED}$.

---

## 8. Scheduler Methodology
- **Static**: Fixed AP assignment. Outage on blockage.
- **Reactive**: Reallocates AP only when active link is blocked ($Q < 0.15$).
- **Dynamic**: Multi-objective score maximization:
  $$\text{Score}(u, AP_i) = w_1 Q_{u,i} + w_2 D_{u,i} + w_3 P_u + w_4 F_i - w_5 L_i - w_6 H_{u,i}$$

---

## 9. SLM-Inspired Model
- Calculates 2D phase-gradient array $\Phi(x,y) \in [0, 2\pi]$ steering optical wavefront towards user azimuth direction.
- Computes 2D FFT intensity $|FFT(e^{i \Phi})|^2$ to show far-field diffraction spot position shift.

---

## 10. Metrics
- **Connectivity Ratio (%)**: Percentage of users connected to valid APs.
- **Jain's Fairness Index**: $J = \frac{(\sum x_i)^2}{n \sum x_i^2}$ evaluating throughput distribution.
- **Simulated Throughput (Mbps)**: Max 100 Mbps scaled by optical link quality $Q$.
- **Handovers**: Total beam reassignments.
- **Reallocation Latency**: Simulated decision delay (~20-40 ms).

---

## 11. Demonstration Scenarios
1. **Free Movement**: Random walk multi-user simulation.
2. **Walking Through Beam (Main Demo)**: User 1 walks across obstacle blocking AP1 $\to$ dynamic reallocation to AP2 $\to$ SLM phase angle shift.
3. **High Density**: 18 users, AP capacity load balancing.
4. **Multiple Blockages**: Complex multi-obstacle environment.

---

## 12. Installation & Quick Start

### Step 1: Navigate to Project Directory
```bash
cd D:\lifi-digital-twin
```

### Step 2: Install Requirements
```bash
pip install -r requirements.txt
```

### Step 3: Launch Interactive Dashboard
```bash
streamlit run app.py
```

---

## 13. Limitations & Future Improvements
- **Limitations**: Simplified 2D geometry for blockage projection, software-only simulation.
- **Future Improvements**: 3D ray-tracing for NLoS reflections, real-time SLM hardware integration over Ethernet/USB, machine learning predictive mobility forecasting.
