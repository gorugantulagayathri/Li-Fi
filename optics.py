"""
Optical Wireless Channel Model & Geometric Blockage Engine.
Implements Lambertian emission, photodiode FOV, distance attenuation, and obstacle blockage detection.
"""

import math
from dataclasses import dataclass
from typing import Dict, Tuple, List
from environment import AccessPoint, Obstacle
from users import User
from utils import line_intersects_rectangle, distance_3d, calculate_angles_3d
from config import (
    SEMI_ANGLE_HALF_POWER, RECEIVER_FOV, DETECTOR_AREA, 
    OPTICAL_POWER_PT, QUALITY_CONNECTED_MIN, QUALITY_DEGRADED_MIN
)

@dataclass
class LinkState:
    ap_id: str
    user_id: str
    distance: float
    angle_deg: float
    azimuth_rad: float
    is_blocked: bool
    is_in_fov: bool
    link_quality: float  # 0.0 to 1.0
    status: str  # CONNECTED, DEGRADED, BLOCKED, UNAVAILABLE
    throughput_mbps: float

class OpticalChannelModel:
    def __init__(self, semi_angle_deg: float = SEMI_ANGLE_HALF_POWER, fov_deg: float = RECEIVER_FOV):
        self.semi_angle_deg = semi_angle_deg
        self.fov_deg = fov_deg
        # Lambertian mode number m = -ln(2) / ln(cos(phi_half))
        phi_half_rad = math.radians(semi_angle_deg)
        self.m = -math.log(2.0) / math.log(max(math.cos(phi_half_rad), 1e-4))
        self.fov_rad = math.radians(fov_deg)

    def evaluate_link(self, ap: AccessPoint, user: User, obstacles: Dict[str, Obstacle]) -> LinkState:
        """
        Calculates optical link parameters between AP and User, checking geometric LOS blockage against obstacles.
        """
        ap_pos = (ap.x, ap.y, ap.z)
        user_pos = (user.x, user.y, user.z)

        # 1. Geometry: 3D distance and angles
        dist = distance_3d(ap_pos, user_pos)
        theta_rad, psi_rad, azimuth_rad = calculate_angles_3d(ap_pos, user_pos)
        angle_deg = math.degrees(theta_rad)

        # FOV check
        is_in_fov = (psi_rad <= self.fov_rad)

        # 2. Geometric Line-of-Sight Blockage Check
        p1 = (ap.x, ap.y)
        p2 = (user.x, user.y)
        
        is_blocked = False
        blocking_obs_id = None

        for obs in obstacles.values():
            rx, ry, rw, rh = obs.bounds_2d
            if line_intersects_rectangle(p1, p2, rx, ry, rw, rh):
                is_blocked = True
                blocking_obs_id = obs.id
                break

        # 3. Lambertian Link Quality Calculation
        if is_blocked or not is_in_fov or dist > ap.coverage_radius + 2.0:
            link_quality = 0.0
            status = "BLOCKED" if is_blocked else "UNAVAILABLE"
            throughput_mbps = 0.0
        else:
            # Lambertian DC channel gain H(0) model
            # H(0) proportional to ((m+1)*A / (2*pi*d^2)) * cos^m(theta) * cos(psi)
            cos_theta = math.cos(theta_rad)
            cos_psi = math.cos(psi_rad)

            # Distance normalization factor (at d=2.0m, theta=0 => H=1.0)
            ref_dist = 2.0
            dist_factor = (ref_dist / max(dist, 1.0)) ** 2
            gain_factor = (cos_theta ** self.m) * cos_psi

            raw_quality = dist_factor * gain_factor
            link_quality = min(1.0, max(0.0, raw_quality))

            # Determine connection status classification
            if link_quality >= QUALITY_CONNECTED_MIN:
                status = "CONNECTED"
            elif link_quality >= QUALITY_DEGRADED_MIN:
                status = "DEGRADED"
            else:
                status = "DEGRADED"

            # Simulated throughput based on optical link SNR / link quality
            # Max throughput per beam: 100 Mbps scaled by link quality
            throughput_mbps = round(link_quality * 100.0, 1)

        return LinkState(
            ap_id=ap.id,
            user_id=user.id,
            distance=round(dist, 2),
            angle_deg=round(angle_deg, 1),
            azimuth_rad=azimuth_rad,
            is_blocked=is_blocked,
            is_in_fov=is_in_fov,
            link_quality=round(link_quality, 3),
            status=status,
            throughput_mbps=throughput_mbps
        )
