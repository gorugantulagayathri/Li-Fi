"""
Performance Metrics Tracker for Li-Fi Digital Twin.
Calculates Connectivity, Jain's Fairness Index, Throughput, Outages, and Latency.
"""

import math
from dataclasses import dataclass, field
from typing import List, Dict, Any
from users import User

@dataclass
class NetworkMetrics:
    connectivity_ratio: float  # Percentage 0-100%
    active_beams: int
    blocked_links: int
    outage_users: int
    total_handovers: int
    avg_throughput_mbps: float
    total_throughput_mbps: float
    jains_fairness_index: float  # 0.0 to 1.0
    avg_reallocation_latency_ms: float

class MetricsEngine:
    def __init__(self):
        self.history_timestamps: List[float] = []
        self.history_connectivity: List[float] = []
        self.history_throughput: List[float] = []
        self.history_fairness: List[float] = []

    def calculate_metrics(self, users: Dict[str, User], sim_time: float) -> NetworkMetrics:
        if not users:
            return NetworkMetrics(0.0, 0, 0, 0, 0, 0.0, 0.0, 1.0, 0.0)

        total_users = len(users)
        connected_count = 0
        blocked_count = 0
        outage_count = 0
        total_handovers = 0
        throughputs: List[float] = []

        for u in users.values():
            throughputs.append(u.throughput_mbps)
            total_handovers += u.handover_count

            if u.connection_state in ["CONNECTED", "DEGRADED"]:
                connected_count += 1
            elif u.connection_state == "BLOCKED":
                blocked_count += 1
                outage_count += 1
            else:
                outage_count += 1

        conn_ratio = (connected_count / total_users) * 100.0
        avg_tp = sum(throughputs) / total_users
        total_tp = sum(throughputs)

        # Jain's Fairness Index calculation
        # J = (sum(x_i))^2 / (n * sum(x_i^2))
        sum_x = sum(throughputs)
        sum_sq_x = sum(x*x for x in throughputs)
        if sum_sq_x > 0:
            jains_fairness = (sum_x ** 2) / (total_users * sum_sq_x)
        else:
            jains_fairness = 1.0

        # Simulated reallocation latency (average 20ms - 40ms)
        avg_latency_ms = 24.5 if total_handovers > 0 else 0.0

        # Save history time series
        self.history_timestamps.append(round(sim_time, 2))
        self.history_connectivity.append(round(conn_ratio, 1))
        self.history_throughput.append(round(avg_tp, 1))
        self.history_fairness.append(round(jains_fairness, 3))

        # Keep history buffer capped at 100 frames
        if len(self.history_timestamps) > 100:
            self.history_timestamps.pop(0)
            self.history_connectivity.pop(0)
            self.history_throughput.pop(0)
            self.history_fairness.pop(0)

        return NetworkMetrics(
            connectivity_ratio=round(conn_ratio, 1),
            active_beams=connected_count,
            blocked_links=blocked_count,
            outage_users=outage_count,
            total_handovers=total_handovers,
            avg_throughput_mbps=round(avg_tp, 1),
            total_throughput_mbps=round(total_tp, 1),
            jains_fairness_index=round(jains_fairness, 3),
            avg_reallocation_latency_ms=avg_latency_ms
        )
