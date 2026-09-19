"""
User model and mobility engine supporting Random Walk, Directed Movement, and Trajectory trails.
"""

import math
import random
from dataclasses import dataclass, field
from typing import List, Tuple, Optional
from config import DEFAULT_USER_HEIGHT, DEFAULT_ROOM_WIDTH, DEFAULT_ROOM_HEIGHT

@dataclass
class User:
    id: str
    x: float
    y: float
    z: float = DEFAULT_USER_HEIGHT
    vx: float = 0.0
    vy: float = 0.0
    speed: float = 1.0  # m/s
    direction_rad: float = 0.0
    movement_mode: str = "Random Walk"  # "Random Walk", "Directed", "Scenario"
    target_waypoint: Optional[Tuple[float, float]] = None
    priority: int = 1  # 1 (Normal), 2 (High), 3 (VIP)
    
    current_ap: Optional[str] = None
    connection_state: str = "UNAVAILABLE"  # CONNECTED, DEGRADED, BLOCKED, UNAVAILABLE
    link_quality: float = 0.0  # 0.0 to 1.0
    throughput_mbps: float = 0.0
    outage_duration: float = 0.0
    handover_count: int = 0
    history: List[Tuple[float, float]] = field(default_factory=list)
    max_history_len: int = 15
    
    # Advanced features
    predicted_blockage: bool = False
    blockage_warning_ap: Optional[str] = None

    def __post_init__(self):
        if not self.history:
            self.history.append((self.x, self.y))
        if self.direction_rad == 0.0 and (self.vx != 0 or self.vy != 0):
            self.direction_rad = math.atan2(self.vy, self.vx)
        elif self.vx == 0 and self.vy == 0:
            self.direction_rad = random.uniform(0, 2 * math.pi)
            self.vx = self.speed * math.cos(self.direction_rad)
            self.vy = self.speed * math.sin(self.direction_rad)

    def set_velocity_from_direction(self, speed: float, direction_rad: float):
        self.speed = speed
        self.direction_rad = direction_rad
        self.vx = speed * math.cos(direction_rad)
        self.vy = speed * math.sin(direction_rad)

    def update_position(self, dt: float, room_width: float = DEFAULT_ROOM_WIDTH, room_height: float = DEFAULT_ROOM_HEIGHT):
        """Update user position based on movement mode and time step dt."""
        if self.movement_mode == "Random Walk":
            # Small random angle perturbation
            self.direction_rad += random.uniform(-0.35, 0.35)
            self.vx = self.speed * math.cos(self.direction_rad)
            self.vy = self.speed * math.sin(self.direction_rad)

        elif self.movement_mode == "Directed" and self.target_waypoint is not None:
            tx, ty = self.target_waypoint
            dx = tx - self.x
            dy = ty - self.y
            dist = math.sqrt(dx*dx + dy*dy)
            if dist > 0.3:
                self.direction_rad = math.atan2(dy, dx)
                self.vx = self.speed * math.cos(self.direction_rad)
                self.vy = self.speed * math.sin(self.direction_rad)
            else:
                # Reached waypoint
                self.vx = 0.0
                self.vy = 0.0

        # Step calculation
        new_x = self.x + self.vx * dt
        new_y = self.y + self.vy * dt

        # Boundary bouncing (stay inside room borders)
        margin = 0.5
        bounced = False
        if new_x <= margin:
            new_x = margin
            self.vx = abs(self.vx)
            bounced = True
        elif new_x >= room_width - margin:
            new_x = room_width - margin
            self.vx = -abs(self.vx)
            bounced = True

        if new_y <= margin:
            new_y = margin
            self.vy = abs(self.vy)
            bounced = True
        elif new_y >= room_height - margin:
            new_y = room_height - margin
            self.vy = -abs(self.vy)
            bounced = True

        if bounced:
            self.direction_rad = math.atan2(self.vy, self.vx)

        self.x = new_x
        self.y = new_y

        # Append to position trail
        self.history.append((self.x, self.y))
        if len(self.history) > self.max_history_len:
            self.history.pop(0)

class UserManager:
    def __init__(self):
        self.users: Dict[str, User] = {}

    def add_user(self, user: User):
        self.users[user.id] = user

    def create_default_users(self, num_users: int = 6, room_width: float = DEFAULT_ROOM_WIDTH, room_height: float = DEFAULT_ROOM_HEIGHT):
        self.users.clear()
        
        # User priorities distribution
        priorities = [1, 2, 3, 1, 1, 2, 1, 3]

        for i in range(num_users):
            u_id = f"U{i+1}"
            # Scatter users across room
            x = random.uniform(2.0, room_width - 2.0)
            y = random.uniform(2.0, room_height - 2.0)
            speed = random.uniform(0.6, 1.4)
            prio = priorities[i % len(priorities)]
            
            user = User(
                id=u_id,
                x=x,
                y=y,
                speed=speed,
                priority=prio,
                movement_mode="Random Walk"
            )
            self.add_user(user)

    def update_all_positions(self, dt: float, room_width: float, room_height: float):
        for user in self.users.values():
            user.update_position(dt, room_width, room_height)
