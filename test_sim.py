"""
Validation script to test all simulation modules, geometry checks, optics, scheduler, SLM phase mask, and scenario engine.
"""

import sys
import numpy as np

def run_tests():
    print("=== 1. Testing Utilities & Geometry ===")
    from utils import line_intersects_rectangle, distance_3d
    # Test line crossing rectangle (0,0)->(10,10) crossing rect at (4,4,2,2)
    hit = line_intersects_rectangle((0.0, 0.0), (10.0, 10.0), 4.0, 4.0, 2.0, 2.0)
    assert hit == True, "Geometry check failed for intersecting line!"
    no_hit = line_intersects_rectangle((0.0, 0.0), (2.0, 2.0), 5.0, 5.0, 2.0, 2.0)
    assert no_hit == False, "Geometry check failed for non-intersecting line!"
    print("Geometry check PASSED.")

    print("\n=== 2. Testing Environment & Users ===")
    from environment import Environment, AccessPoint, Obstacle
    from users import UserManager, User
    env = Environment.create_default(num_aps=3, num_obstacles=3)
    user_mgr = UserManager()
    user_mgr.create_default_users(num_users=6, room_width=20.0, room_height=12.0)
    assert len(env.aps) == 3
    assert len(user_mgr.users) == 6
    print("Environment & Users initialization PASSED.")

    print("\n=== 3. Testing Optical Channel & Blockage ===")
    from optics import OpticalChannelModel
    optics = OpticalChannelModel()
    ap1 = list(env.aps.values())[0]
    u1 = list(user_mgr.users.values())[0]
    link_state = optics.evaluate_link(ap1, u1, env.obstacles)
    assert hasattr(link_state, "link_quality")
    print(f"Optical link state evaluated: AP {ap1.id} -> User {u1.id}, Q={link_state.link_quality:.2f}, Status={link_state.status}")
    print("Optical Channel Model PASSED.")

    print("\n=== 4. Testing Scheduler (Static, Reactive, Dynamic) ===")
    from scheduler import BeamScheduler
    for mode in ["Static", "Reactive", "Dynamic"]:
        scheduler = BeamScheduler(mode=mode)
        decision = scheduler.schedule_user(u1, env, optics)
        assert decision.decision_type in ["INITIAL", "MAINTAINED", "REASSIGNED", "OUTAGE"]
        print(f"Scheduler mode '{mode}' PASSED. Decision: {decision.decision_type} - {decision.reason}")

    print("\n=== 5. Testing SLM Phase Mask & Far-Field FFT ===")
    from slm import SLMPhaseMaskModel
    slm = SLMPhaseMaskModel(grid_size=32)
    phase_mask = slm.calculate_phase_mask(azimuth_rad=0.5)
    assert phase_mask.shape == (32, 32)
    assert np.min(phase_mask) >= 0.0 and np.max(phase_mask) <= 2.0 * np.pi
    far_field = slm.calculate_far_field_diffraction(phase_mask)
    assert far_field.shape == (32, 32)
    print("SLM Phase Mask & FFT Far-Field PASSED.")

    print("\n=== 6. Testing Simulation Engine Step Loop ===")
    from simulation import SimulationEngine
    sim = SimulationEngine(mode="Dynamic")
    for step_i in range(10):
        sim.step()
    assert sim.sim_time > 0
    assert sim.current_metrics is not None
    print(f"10 simulation steps executed successfully. Sim time = {sim.sim_time:.2f}s, Connectivity = {sim.current_metrics.connectivity_ratio}%")

    print("\n=== 7. Testing Scenarios Engine ===")
    from scenarios import ScenarioEngine
    for scenario_name in ["Free Movement", "Walking Through Beam", "High Density", "Multiple Blockages"]:
        ScenarioEngine.setup_scenario(scenario_name, sim.env, sim.user_mgr)
        sim.step()
        print(f"Scenario '{scenario_name}' initialized & stepped successfully.")

    print("\n==========================================")
    print("ALL 7 SYSTEM TEST SUITES PASSED CLEANLY!")
    print("==========================================")

if __name__ == "__main__":
    run_tests()
