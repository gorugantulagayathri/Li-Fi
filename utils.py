"""
Utility functions for geometry, line-of-sight blockage checks, vector math, and logging.
"""

import math
from typing import Tuple, List, Dict, Any, Optional

def segments_intersect(p1: Tuple[float, float], p2: Tuple[float, float], 
                       q1: Tuple[float, float], q2: Tuple[float, float]) -> bool:
    """Check if 2D line segment p1-p2 intersects line segment q1-q2."""
    def ccw(A, B, C):
        return (C[1]-A[1]) * (B[0]-A[0]) > (B[1]-A[1]) * (C[0]-A[0])
    
    # Standard cross product counter-clockwise orientation check
    return (ccw(p1, q1, q2) != ccw(p2, q1, q2)) and (ccw(p1, p2, q1) != ccw(p1, p2, q2))

def point_in_rectangle(px: float, py: float, rx: float, ry: float, rw: float, rh: float) -> bool:
    """Check if point (px, py) lies inside or on boundary of rectangle (rx, ry, rw, rh)."""
    return (rx <= px <= rx + rw) and (ry <= py <= ry + rh)

def line_intersects_rectangle(p1: Tuple[float, float], p2: Tuple[float, float],
                              rx: float, ry: float, rw: float, rh: float) -> bool:
    """
    Robust 2D line segment to axis-aligned rectangle intersection test.
    Returns True if line segment between p1 and p2 intersects rectangle (rx, ry, rw, rh).
    """
    # 1. If either endpoint is inside rectangle
    if point_in_rectangle(p1[0], p1[1], rx, ry, rw, rh) or point_in_rectangle(p2[0], p2[1], rx, ry, rw, rh):
        return True
    
    # 2. Check intersection with 4 rectangle boundary edges
    r1 = (rx, ry)
    r2 = (rx + rw, ry)
    r3 = (rx + rw, ry + rh)
    r4 = (rx, ry + rh)

    if segments_intersect(p1, p2, r1, r2): return True
    if segments_intersect(p1, p2, r2, r3): return True
    if segments_intersect(p1, p2, r3, r4): return True
    if segments_intersect(p1, p2, r4, r1): return True

    return False

def distance_3d(pos1: Tuple[float, float, float], pos2: Tuple[float, float, float]) -> float:
    """Calculate 3D Euclidean distance between two points (x, y, z)."""
    dx = pos1[0] - pos2[0]
    dy = pos1[1] - pos2[1]
    dz = pos1[2] - pos2[2]
    return math.sqrt(dx*dx + dy*dy + dz*dz)

def distance_2d(pos1: Tuple[float, float], pos2: Tuple[float, float]) -> float:
    """Calculate 2D Euclidean distance between two points (x, y)."""
    dx = pos1[0] - pos2[0]
    dy = pos1[1] - pos2[1]
    return math.sqrt(dx*dx + dy*dy)

def calculate_angles_3d(ap_pos: Tuple[float, float, float], user_pos: Tuple[float, float, float]) -> Tuple[float, float, float]:
    """
    Calculate optical angles:
    - theta_rad: Emission angle from zenith (perpendicular ceiling downward)
    - psi_rad: Incidence angle at receiver photodiode (facing straight up)
    - azimuth_rad: 2D direction angle in XY plane
    """
    dx = user_pos[0] - ap_pos[0]
    dy = user_pos[1] - ap_pos[1]
    dz = abs(ap_pos[2] - user_pos[2])  # vertical height difference
    dist = distance_3d(ap_pos, user_pos)

    if dist < 1e-6:
        return 0.0, 0.0, 0.0

    # Emission / incidence angle (assuming AP points down -z, User photodiode points up +z)
    cos_angle = dz / dist
    angle_rad = math.acos(min(max(cos_angle, 0.0), 1.0))
    
    azimuth_rad = math.atan2(dy, dx)
    
    return angle_rad, angle_rad, azimuth_rad

def format_event_log(sim_time: float, component: str, message: str, status: str = "INFO") -> Dict[str, Any]:
    """Structure event log entry for dashboard display."""
    return {
        "timestamp": f"{sim_time:.2f}s",
        "time_val": sim_time,
        "component": component,
        "message": message,
        "status": status
    }
