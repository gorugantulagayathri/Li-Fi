"""
Simulation Engine orchestrating simulation clock, state updates, optical evaluation,
predictive blockage warning, dynamic scheduler triggers, and event logging.
"""

from typing import List, Dict, Any, Optional, Tuple
from environment import Environment
from users import UserManager, User
from optics import OpticalChannelModel, LinkState
from scheduler import BeamScheduler, SchedulerDecision
from slm import SLMPhaseMaskModel
from metrics import MetricsEngine, NetworkMetrics
from utils import format_event_log, line_intersects_rectangle, distance_2d

class SimulationEngine:
    def __init__(self, mode: str = "Dynamic"):
        self.sim_time: float = 0.0
        self.dt: float = 0.2  # step delta in seconds
        self.is_running: bool = True
        self.speed_multiplier: float = 1.0
        self.selected_scenario: str = "Free Movement"

        self.env = Environment.create_default()
        self.user_mgr = UserManager()
        self.user_mgr.create_default_users(num_users=6, room_width=self.env.width, room_height=self.env.height)
        
        self.optics = OpticalChannelModel()
        self.scheduler = BeamScheduler(mode=mode)
        self.slm = SLMPhaseMaskModel()
        self.metrics_engine = MetricsEngine()

        self.event_log: List[Dict[str, Any]] = []
        self.last_decisions: Dict[str, SchedulerDecision] = {}
        self.current_metrics: Optional[NetworkMetrics] = None

        # Log initial startup
        self.log_event("SYSTEM", f"Simulation initialized with {len(self.user_mgr.users)} users and {len(self.env.aps)} APs. Scheduler mode: {self.scheduler.mode}", "SUCCESS")

    def log_event(self, component: str, message: str, status: str = "INFO"):
        entry = format_event_log(self.sim_time, component, message, status)
        self.event_log.insert(0, entry)
        if len(self.event_log) > 100:
            self.event_log.pop()

    def set_scheduler_mode(self, mode: str):
        if self.scheduler.mode != mode:
            self.scheduler.mode = mode
            self.log_event("SCHEDULER", f"Scheduling mode switched to {mode}", "WARNING")

    def predict_blockage_warnings(self):
        """
        Predictive blockage warning:
        Projects user position 1.5 seconds into the future along current velocity vector.
        If projected line segment from active AP intersects an obstacle, raises warning.
        """
        pred_time = 1.5  # seconds ahead
        for u in self.user_mgr.users.values():
            u.predicted_blockage = False
            u.blockage_warning_ap = None

            if not u.current_ap or u.current_ap not in self.env.aps:
                continue

            ap = self.env.aps[u.current_ap]
            # Projected future position
            px = u.x + u.vx * pred_time
            py = u.y + u.vy * pred_time

            # Line segment from AP to projected position
            p1 = (ap.x, ap.y)
            p2 = (px, py)

            for obs in self.env.obstacles.values():
                if line_intersects_rectangle(p1, p2, *obs.bounds_2d):
                    u.predicted_blockage = True
                    u.blockage_warning_ap = ap.id
                    break

    def step(self):
        """Execute single simulation tick."""
        if not self.is_running:
            return

        effective_dt = self.dt * self.speed_multiplier
        self.sim_time += effective_dt

        # 1. Update user movement positions
        self.user_mgr.update_all_positions(effective_dt, self.env.width, self.env.height)

        # 2. Run predictive blockage detection
        self.predict_blockage_warnings()

        # 3. Evaluate optical links & execute scheduler for each user
        for u in self.user_mgr.users.values():
            prev_ap = u.current_ap
            prev_state = u.connection_state

            # Schedule user
            decision = self.scheduler.schedule_user(u, self.env, self.optics)
            self.last_decisions[u.id] = decision

            # Track outage duration
            if u.connection_state in ["BLOCKED", "OUTAGE", "UNAVAILABLE"]:
                u.outage_duration += effective_dt

            # Log events upon state transition
            if prev_state != u.connection_state:
                if u.connection_state == "BLOCKED":
                    self.log_event("OPTICS", f"{u.id} -> {prev_ap or 'AP'} OPTICAL LOS BLOCKED by obstacle", "ERROR")
                    if self.scheduler.mode != "Static":
                        self.log_event("SCHEDULER", f"Triggering handover search for {u.id}...", "WARNING")
                elif u.connection_state == "DEGRADED":
                    self.log_event("OPTICS", f"{u.id} -> {u.current_ap} link DEGRADED (Q={u.link_quality:.2f})", "WARNING")

            if decision.decision_type == "REASSIGNED":
                self.log_event("SCHEDULER", f"Beam Reallocated: {u.id} {decision.previous_ap or 'None'} -> {decision.assigned_ap} ({decision.reason})", "SUCCESS")
                self.log_event("SLM", f"SLM Phase Mask updated angle for {u.id} beam on {decision.assigned_ap}", "INFO")

        # 4. Calculate system performance metrics
        self.current_metrics = self.metrics_engine.calculate_metrics(self.user_mgr.users, self.sim_time)

    def reset(self):
        self.sim_time = 0.0
        self.event_log.clear()
        self.last_decisions.clear()
        self.env.reset_assignments()
        self.user_mgr.create_default_users(num_users=len(self.user_mgr.users) or 6, room_width=self.env.width, room_height=self.env.height)
        self.log_event("SYSTEM", "Simulation state reset.", "INFO")
