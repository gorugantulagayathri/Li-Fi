"""
Configuration module for Li-Fi Digital Twin simulation.
Contains default parameters for room, access points, obstacles, optics, and scheduler.
"""

# Room Environment Dimensions (meters)
DEFAULT_ROOM_WIDTH = 20.0
DEFAULT_ROOM_HEIGHT = 12.0
DEFAULT_ROOM_CEILING = 3.0
DEFAULT_USER_HEIGHT = 1.0  # Receiver height (desk level)

# Access Point Defaults
DEFAULT_AP_HEIGHT = 3.0  # Mounted on ceiling
DEFAULT_AP_COVERAGE_RADIUS = 8.0  # meters
DEFAULT_AP_MAX_CAPACITY = 8  # max users per AP
DEFAULT_AP_BEAM_CAPACITY = 8

# Optical Channel Defaults
SEMI_ANGLE_HALF_POWER = 60.0  # degrees (LED emission semi-angle)
RECEIVER_FOV = 60.0  # degrees (Photodiode Field of View)
DETECTOR_AREA = 1e-4  # m^2 (1 cm^2 photodiode area)
OPTICAL_POWER_PT = 10.0  # Watts emitted power
OPTICAL_RESPONSIVITY = 0.6  # A/W photodiode responsivity

# Link Quality Thresholds
QUALITY_CONNECTED_MIN = 0.6
QUALITY_DEGRADED_MIN = 0.15

# Dynamic Scheduler Weights (Default)
DEFAULT_WEIGHT_LINK_QUALITY = 0.40
DEFAULT_WEIGHT_DISTANCE = 0.15
DEFAULT_WEIGHT_PRIORITY = 0.15
DEFAULT_WEIGHT_FAIRNESS = 0.10
DEFAULT_WEIGHT_LOAD_PENALTY = 0.10
DEFAULT_WEIGHT_HANDOVER_COST = 0.10

# SLM Computational Model Defaults
SLM_GRID_SIZE = 64
OPTICAL_WAVELENGTH_NM = 850.0  # Infrared / Visible wavelength in nm
