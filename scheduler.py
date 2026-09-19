"""
Beam Scheduler Module supporting Static, Reactive, and Dynamic Multi-Objective Scheduling Modes.
Provides transparent explanations for all beam allocation decisions.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any
from environment import Environment, AccessPoint
from users import User
from optics import OpticalChannelModel, LinkState
from config import (
    DEFAULT_WEIGHT_LINK_QUALITY, DEFAULT_WEIGHT_DISTANCE, DEFAULT_WEIGHT_PRIORITY,
    DEFAULT_WEIGHT_FAIRNESS, DEFAULT_WEIGHT_LOAD_PENALTY, DEFAULT_WEIGHT_HANDOVER_COST
)

@dataclass
class SchedulerDecision:
    user_id: str
    previous_ap: Optional[str]
    assigned_ap: Optional[str]
    decision_type: str  # "INITIAL", "MAINTAINED", "REASSIGNED", "OUTAGE"
    reason: str
    detailed_scores: Dict[str, float] = field(default_factory=dict)
    candidate_breakdown: List[Dict[str, Any]] = field(default_factory=list)

class BeamScheduler:
    def __init__(self, mode: str = "Dynamic"):
        self.mode = mode  # "Static", "Reactive", "Dynamic"
        self.w_quality = DEFAULT_WEIGHT_LINK_QUALITY
        self.w_distance = DEFAULT_WEIGHT_DISTANCE
        self.w_priority = DEFAULT_WEIGHT_PRIORITY
        self.w_fairness = DEFAULT_WEIGHT_FAIRNESS
        self.w_load = DEFAULT_WEIGHT_LOAD_PENALTY
        self.w_handover = DEFAULT_WEIGHT_HANDOVER_COST

    def set_weights(self, w_quality: float, w_distance: float, w_priority: float,
                    w_fairness: float, w_load: float, w_handover: float):
        self.w_quality = w_quality
        self.w_distance = w_distance
        self.w_priority = w_priority
        self.w_fairness = w_fairness
        self.w_load = w_load
        self.w_handover = w_handover

    def schedule_user(self, user: User, env: Environment, optics: OpticalChannelModel) -> SchedulerDecision:
        """
        Executes beam assignment for a given user based on current scheduling mode.
        """
        # Evaluate links from all APs to this user
        link_states: Dict[str, LinkState] = {}
        for ap_id, ap in env.aps.items():
            link_states[ap_id] = optics.evaluate_link(ap, user, env.obstacles)

        curr_ap_id = user.current_ap

        if self.mode == "Static":
            return self._schedule_static(user, env, link_states, curr_ap_id)
        elif self.mode == "Reactive":
            return self._schedule_reactive(user, env, link_states, curr_ap_id)
        else:  # Dynamic
            return self._schedule_dynamic(user, env, link_states, curr_ap_id)

    def _schedule_static(self, user: User, env: Environment, link_states: Dict[str, LinkState], curr_ap_id: Optional[str]) -> SchedulerDecision:
        # Initial assignment if none
        if curr_ap_id is None:
            # Pick closest AP with clear LOS
            candidates = [ls for ls in link_states.values() if not ls.is_blocked]
            if candidates:
                best = max(candidates, key=lambda ls: ls.link_quality)
                env.aps[best.ap_id].assign_user(user.id, best.azimuth_rad)
                user.current_ap = best.ap_id
                user.connection_state = best.status
                user.link_quality = best.link_quality
                user.throughput_mbps = best.throughput_mbps
                return SchedulerDecision(user.id, None, best.ap_id, "INITIAL", f"Static initial assignment to {best.ap_id}")
            else:
                user.current_ap = None
                user.connection_state = "OUTAGE"
                user.link_quality = 0.0
                user.throughput_mbps = 0.0
                return SchedulerDecision(user.id, None, None, "OUTAGE", "No optical path available for static assignment")
        
        # Static mode: Keep current AP regardless of blockage
        current_link = link_states.get(curr_ap_id)
        if current_link and not current_link.is_blocked and current_link.status != "UNAVAILABLE":
            user.connection_state = current_link.status
            user.link_quality = current_link.link_quality
            user.throughput_mbps = current_link.throughput_mbps
            return SchedulerDecision(user.id, curr_ap_id, curr_ap_id, "MAINTAINED", f"Static mode: connection maintained on {curr_ap_id}")
        else:
            # Blocked in static mode -> Outage (no handover allowed in static mode)
            user.connection_state = "BLOCKED"
            user.link_quality = 0.0
            user.throughput_mbps = 0.0
            return SchedulerDecision(user.id, curr_ap_id, curr_ap_id, "OUTAGE", f"Static mode: optical link to {curr_ap_id} BLOCKED. Handover disabled.")

    def _schedule_reactive(self, user: User, env: Environment, link_states: Dict[str, LinkState], curr_ap_id: Optional[str]) -> SchedulerDecision:
        current_link = link_states.get(curr_ap_id) if curr_ap_id else None
        
        # If current link is healthy, maintain it
        if current_link and not current_link.is_blocked and current_link.link_quality >= 0.2:
            user.connection_state = current_link.status
            user.link_quality = current_link.link_quality
            user.throughput_mbps = current_link.throughput_mbps
            return SchedulerDecision(user.id, curr_ap_id, curr_ap_id, "MAINTAINED", f"Reactive mode: link to {curr_ap_id} healthy (Q={current_link.link_quality:.2f})")

        # Current link blocked or degraded -> Reactive handover search
        valid_candidates = [
            ls for ls in link_states.values() 
            if not ls.is_blocked and ls.link_quality >= 0.15 and not env.aps[ls.ap_id].is_full
        ]

        if valid_candidates:
            best_cand = max(valid_candidates, key=lambda ls: ls.link_quality)
            if curr_ap_id and curr_ap_id in env.aps:
                env.aps[curr_ap_id].remove_user(user.id)
            
            env.aps[best_cand.ap_id].assign_user(user.id, best_cand.azimuth_rad)
            user.current_ap = best_cand.ap_id
            user.connection_state = best_cand.status
            user.link_quality = best_cand.link_quality
            user.throughput_mbps = best_cand.throughput_mbps
            user.handover_count += 1

            reason = f"Reactive handover: {curr_ap_id or 'None'} -> {best_cand.ap_id} due to blockage/degradation. Best LOS Q={best_cand.link_quality:.2f}"
            return SchedulerDecision(user.id, curr_ap_id, best_cand.ap_id, "REASSIGNED", reason)

        # No valid candidate found
        if curr_ap_id and curr_ap_id in env.aps:
            env.aps[curr_ap_id].remove_user(user.id)
        user.current_ap = None
        user.connection_state = "OUTAGE"
        user.link_quality = 0.0
        user.throughput_mbps = 0.0
        return SchedulerDecision(user.id, curr_ap_id, None, "OUTAGE", "Reactive search failed: No alternative optical path available with LOS.")

    def _schedule_dynamic(self, user: User, env: Environment, link_states: Dict[str, LinkState], curr_ap_id: Optional[str]) -> SchedulerDecision:
        candidate_scores: Dict[str, float] = {}
        breakdown_list: List[Dict[str, Any]] = []

        for ap_id, ap in env.aps.items():
            link = link_states[ap_id]
            if link.is_blocked or link.status == "UNAVAILABLE":
                candidate_scores[ap_id] = -1.0
                breakdown_list.append({
                    "ap_id": ap_id,
                    "score": -1.0,
                    "reason": "LOS Blocked or out of coverage",
                    "link_quality": 0.0,
                    "load_ratio": ap.load_ratio
                })
                continue

            # Capacity check (unless already assigned to this AP)
            if ap.is_full and ap_id != curr_ap_id:
                candidate_scores[ap_id] = -0.5
                breakdown_list.append({
                    "ap_id": ap_id,
                    "score": -0.5,
                    "reason": "AP Capacity Full",
                    "link_quality": link.link_quality,
                    "load_ratio": ap.load_ratio
                })
                continue

            # Multi-objective Score Calculation
            q_score = link.link_quality
            d_score = max(0.0, 1.0 - (link.distance / ap.coverage_radius))
            p_score = user.priority / 3.0
            f_score = 1.0 - ap.load_ratio
            load_penalty = ap.load_ratio
            handover_cost = 1.0 if (curr_ap_id is not None and ap_id != curr_ap_id) else 0.0

            total_score = (
                self.w_quality * q_score +
                self.w_distance * d_score +
                self.w_priority * p_score +
                self.w_fairness * f_score -
                self.w_load * load_penalty -
                self.w_handover * handover_cost
            )

            candidate_scores[ap_id] = total_score
            breakdown_list.append({
                "ap_id": ap_id,
                "score": round(total_score, 3),
                "q_score": round(q_score, 2),
                "d_score": round(d_score, 2),
                "load_ratio": round(ap.load_ratio, 2),
                "handover_cost": handover_cost,
                "reason": f"Clear LOS, Q={q_score:.2f}, Score={total_score:.3f}"
            })

        # Select candidate with highest positive score
        best_ap_id = max(candidate_scores, key=candidate_scores.get)
        best_score = candidate_scores[best_ap_id]

        if best_score <= -0.1:
            # Outage condition
            if curr_ap_id and curr_ap_id in env.aps:
                env.aps[curr_ap_id].remove_user(user.id)
            user.current_ap = None
            user.connection_state = "OUTAGE"
            user.link_quality = 0.0
            user.throughput_mbps = 0.0
            return SchedulerDecision(
                user.id, curr_ap_id, None, "OUTAGE",
                "Dynamic scheduler: No candidate AP provides positive optical score (all paths blocked/full).",
                candidate_breakdown=breakdown_list
            )

        if curr_ap_id != best_ap_id:
            # Handover executed
            if curr_ap_id and curr_ap_id in env.aps:
                env.aps[curr_ap_id].remove_user(user.id)
            env.aps[best_ap_id].assign_user(user.id, link_states[best_ap_id].azimuth_rad)
            user.current_ap = best_ap_id
            user.handover_count += (1 if curr_ap_id is not None else 0)
            decision_type = "REASSIGNED" if curr_ap_id else "INITIAL"
            reason = f"Dynamic score optimum: assigned to {best_ap_id} (Score={best_score:.3f}, Q={link_states[best_ap_id].link_quality:.2f}, AP load={env.aps[best_ap_id].current_load}/{env.aps[best_ap_id].max_capacity})"
        else:
            # Maintained
            env.aps[best_ap_id].beam_angles[user.id] = link_states[best_ap_id].azimuth_rad
            decision_type = "MAINTAINED"
            reason = f"Maintained optimal beam on {best_ap_id} (Score={best_score:.3f})"

        best_link = link_states[best_ap_id]
        user.connection_state = best_link.status
        user.link_quality = best_link.link_quality
        user.throughput_mbps = best_link.throughput_mbps

        return SchedulerDecision(
            user.id, curr_ap_id, best_ap_id, decision_type, reason,
            detailed_scores=candidate_scores, candidate_breakdown=breakdown_list
        )
