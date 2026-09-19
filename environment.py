"""
Environment module containing AccessPoint, Obstacle dataclasses, and Environment manager.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from config import DEFAULT_ROOM_WIDTH, DEFAULT_ROOM_HEIGHT, DEFAULT_ROOM_CEILING, DEFAULT_AP_HEIGHT, DEFAULT_AP_COVERAGE_RADIUS, DEFAULT_AP_MAX_CAPACITY

@dataclass
class AccessPoint:
    id: str
    x: float
    y: float
    z: float = DEFAULT_AP_HEIGHT
    coverage_radius: float = DEFAULT_AP_COVERAGE_RADIUS
    max_capacity: int = DEFAULT_AP_MAX_CAPACITY
    assigned_users: List[str] = field(default_factory=list)
    beam_angles: Dict[str, float] = field(default_factory=dict)  # user_id -> azimuth angle

    @property
    def current_load(self) -> int:
        return len(self.assigned_users)

    @property
    def load_ratio(self) -> float:
        return self.current_load / max(1, self.max_capacity)

    @property
    def is_full(self) -> bool:
        return self.current_load >= self.max_capacity

    def assign_user(self, user_id: str, azimuth_rad: float = 0.0):
        if user_id not in self.assigned_users:
            self.assigned_users.append(user_id)
        self.beam_angles[user_id] = azimuth_rad

    def remove_user(self, user_id: str):
        if user_id in self.assigned_users:
            self.assigned_users.remove(user_id)
        if user_id in self.beam_angles:
            del self.beam_angles[user_id]

@dataclass
class Obstacle:
    id: str
    label: str
    x: float
    y: float
    width: float
    height: float
    height_z: float = 2.0  # Height in Z dimension

    @property
    def bounds_2d(self) -> Tuple[float, float, float, float]:
        """(x, y, width, height)"""
        return (self.x, self.y, self.width, self.height)

class Environment:
    def __init__(self, width: float = DEFAULT_ROOM_WIDTH, height: float = DEFAULT_ROOM_HEIGHT, ceiling: float = DEFAULT_ROOM_CEILING):
        self.width = width
        self.height = height
        self.ceiling = ceiling
        self.aps: Dict[str, AccessPoint] = {}
        self.obstacles: Dict[str, Obstacle] = {}

    def add_ap(self, ap: AccessPoint):
        self.aps[ap.id] = ap

    def add_obstacle(self, obstacle: Obstacle):
        self.obstacles[obstacle.id] = obstacle

    def reset_assignments(self):
        for ap in self.aps.values():
            ap.assigned_users.clear()
            ap.beam_angles.clear()

    @classmethod
    def create_default(cls, num_aps: int = 3, num_obstacles: int = 3, width: float = DEFAULT_ROOM_WIDTH, height: float = DEFAULT_ROOM_HEIGHT) -> 'Environment':
        env = cls(width=width, height=height)

        # Positioning APs evenly across room ceiling
        if num_aps == 1:
            ap_positions = [(width / 2.0, height / 2.0)]
        elif num_aps == 2:
            ap_positions = [(width * 0.33, height * 0.5), (width * 0.67, height * 0.5)]
        elif num_aps == 3:
            ap_positions = [(width * 0.25, height * 0.5), (width * 0.50, height * 0.5), (width * 0.75, height * 0.5)]
        elif num_aps == 4:
            ap_positions = [
                (width * 0.30, height * 0.35), (width * 0.70, height * 0.35),
                (width * 0.30, height * 0.65), (width * 0.70, height * 0.65)
            ]
        else:
            # Grid placement for > 4 APs
            ap_positions = []
            cols = 3
            rows = max(1, (num_aps + cols - 1) // cols)
            idx = 0
            for r in range(rows):
                for c in range(cols):
                    if idx < num_aps:
                        px = (c + 1) * (width / (cols + 1))
                        py = (r + 1) * (height / (rows + 1))
                        ap_positions.append((px, py))
                        idx += 1

        for i, (x, y) in enumerate(ap_positions):
            ap_id = f"AP{i+1}"
            env.add_ap(AccessPoint(id=ap_id, x=x, y=y))

        # Default realistic indoor obstacles (bookshelves, partitions, pillars)
        default_obstacles = [
            Obstacle(id="OBS1", label="Tall Bookshelf", x=7.5, y=3.0, width=1.2, height=4.5),
            Obstacle(id="OBS2", label="Office Partition", x=12.0, y=5.0, width=1.0, height=5.0),
            Obstacle(id="OBS3", label="Meeting Pod", x=4.0, y=7.5, width=2.5, height=2.0),
            Obstacle(id="OBS4", label="Central Pillar", x=10.0, y=1.5, width=1.5, height=1.5),
            Obstacle(id="OBS5", label="Storage Rack", x=16.0, y=2.0, width=1.5, height=3.5),
        ]

        for obs in default_obstacles[:num_obstacles]:
            env.add_obstacle(obs)

        return env
