"""
Dynamic Li-Fi Beam Scheduling and Load Balancing Simulation
===========================================================
A real-time Pygame simulation demonstrating:
- Multiple Li-Fi Access Points (APs) in a grid with strict user capacities.
- Clustered static library users around designated study tables.
- Dynamic obstacles moving along aisles/lanes with Predictive Warning Zones.
- Proactive Handover (Orange -> Green) triggered before physical blockage.
- Cascading Load Balancing when candidate APs reach maximum capacity.
- Total Network/Physical Failure edge-case handling (Thin Red Line).
"""

import sys
import subprocess
import math
import random
import time

# Ensure immediate terminal printing without buffering delays
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)

# ==========================================
# BOOTSTRAP AUTO-INSTALLER
# ==========================================
def bootstrap_pygame():
    try:
        import pygame  # noqa: F401
    except ImportError:
        print("[BOOTSTRAP] Pygame not found. Silently installing pygame via pip...")
        try:
            subprocess.check_call(
                [sys.executable, "-m", "pip", "install", "pygame"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            print("[BOOTSTRAP] Pygame installed successfully!")
        except Exception as err:
            print(f"[BOOTSTRAP ERROR] Failed to install pygame automatically: {err}")
            sys.exit(1)

bootstrap_pygame()

import pygame

# ==========================================
# CONSTANTS & PALETTE
# ==========================================
WINDOW_WIDTH = 1000
WINDOW_HEIGHT = 1000
FPS = 60

# Design Palette
BG_COLOR = (242, 244, 248)              # Clean library light grey
FLOOR_TILE_COLOR = (235, 238, 243)      # Subtle floor grid
LANE_COLOR = (226, 231, 239)            # Aisles / walkways
LANE_BORDER_COLOR = (210, 216, 226)     # Walkway edge lines
TABLE_COLOR = (218, 224, 233)           # Study table surface
TABLE_BORDER_COLOR = (185, 195, 208)    # Study table border
TEXT_MAIN_COLOR = (30, 41, 59)          # Slate dark
TEXT_MUTED_COLOR = (100, 116, 139)      # Slate muted

# Network & Entity Colors
COLOR_AP = (37, 99, 235)                # Royal Blue AP circles
COLOR_AP_BORDER = (29, 78, 216)
COLOR_USER = (22, 163, 74)              # Green stationary users
COLOR_USER_BORDER = (21, 128, 61)
COLOR_OBSTACLE = (220, 38, 38)          # Solid Red obstacle rectangle
COLOR_OBSTACLE_BORDER = (185, 28, 28)

# Connection Line Colors
COLOR_ACTIVE_BEAM = (34, 197, 94)       # Thick Green active Li-Fi beam
COLOR_THREAT_BEAM = (249, 115, 22)      # Thick Orange imminent threat handover
COLOR_BLOCKED_BEAM = (239, 68, 68)      # Thin Red dropped / physical failure beam

# Capacities and Dimensions
AP_MAX_CAPACITY = 5                     # Max users per AP (Load Balancing threshold)
AP_RADIUS = 15                          # Blue circle radius 15
USER_RADIUS = 8                         # Green circle radius 8
THREAT_FLASH_FRAMES = 25                # Duration to visualize Orange handover threat line
HANDOVER_COOLDOWN_FRAMES = 24           # Hysteresis frames to prevent rapid ping-ponging

# ==========================================
# DATA STRUCTURES & CLASSES
# ==========================================

class AccessPoint:
    def __init__(self, ap_id, x, y, max_capacity=AP_MAX_CAPACITY):
        self.id = ap_id
        self.x = x
        self.y = y
        self.pos = (x, y)
        self.max_capacity = max_capacity
        self.connected_users = []

    @property
    def load(self):
        return len(self.connected_users)

    @property
    def is_full(self):
        return self.load >= self.max_capacity

    def distance_to(self, user_pos):
        return math.hypot(self.x - user_pos[0], self.y - user_pos[1])

    def draw(self, screen, font_small):
        # Draw radio glow / beacon indicator
        glow_surf = pygame.Surface((AP_RADIUS * 4, AP_RADIUS * 4), pygame.SRCALPHA)
        pygame.draw.circle(glow_surf, (37, 99, 235, 35), (AP_RADIUS * 2, AP_RADIUS * 2), AP_RADIUS + 8)
        screen.blit(glow_surf, (self.x - AP_RADIUS * 2, self.y - AP_RADIUS * 2))

        # Blue circle (radius 15)
        pygame.draw.circle(screen, COLOR_AP, self.pos, AP_RADIUS)
        pygame.draw.circle(screen, COLOR_AP_BORDER, self.pos, AP_RADIUS, width=2)
        # Inner white optical diode
        pygame.draw.circle(screen, (255, 255, 255), self.pos, 4)

        # Capacity badge
        load_text = f"{self.load}/{self.max_capacity}"
        is_full = self.is_full
        badge_bg = (239, 68, 68) if is_full else ((245, 158, 11) if self.load == self.max_capacity - 1 else (37, 99, 235))
        
        lbl_surf = font_small.render(f"AP-{self.id + 1}: {load_text}", True, (255, 255, 255))
        w = lbl_surf.get_width() + 10
        h = lbl_surf.get_height() + 4
        badge_rect = pygame.Rect(self.x - w // 2, self.y - AP_RADIUS - 18, w, h)
        pygame.draw.rect(screen, badge_bg, badge_rect, border_radius=4)
        screen.blit(lbl_surf, (self.x - lbl_surf.get_width() // 2, self.y - AP_RADIUS - 16))


class User:
    def __init__(self, user_id, x, y, table_id):
        self.id = user_id
        self.x = x
        self.y = y
        self.pos = (x, y)
        self.table_id = table_id
        
        self.current_ap = None
        self.threatened_ap = None       # AP where imminent threat was detected
        self.threat_timer = 0           # Frames remaining to draw Orange threat line
        self.failed_ap = None           # AP reference when connection drops to Red
        self.is_dropped = False
        self.handover_cooldown = 0      # Frames to prevent ping-pong oscillations

    def draw(self, screen, font_tiny):
        # Green circle (radius 8)
        circle_color = (220, 38, 38) if self.is_dropped else COLOR_USER
        border_color = (185, 28, 28) if self.is_dropped else COLOR_USER_BORDER
        
        pygame.draw.circle(screen, circle_color, self.pos, USER_RADIUS)
        pygame.draw.circle(screen, border_color, self.pos, USER_RADIUS, width=2)
        
        # User ID label
        id_surf = font_tiny.render(f"U{self.id}", True, (255, 255, 255))
        screen.blit(id_surf, (self.x - id_surf.get_width() // 2, self.y - id_surf.get_height() // 2))


class Table:
    def __init__(self, table_id, rect, name):
        self.id = table_id
        self.rect = rect
        self.name = name

    def draw(self, screen, font_small):
        # Table surface
        pygame.draw.rect(screen, TABLE_COLOR, self.rect, border_radius=8)
        pygame.draw.rect(screen, TABLE_BORDER_COLOR, self.rect, width=2, border_radius=8)
        
        # Subtle name badge
        lbl = font_small.render(self.name, True, TEXT_MUTED_COLOR)
        screen.blit(lbl, (self.rect.centerx - lbl.get_width() // 2, self.rect.centery - lbl.get_height() // 2))


class Obstacle:
    def __init__(self, obs_id, x, y, width, height, vx, vy, lane_type, lead_distance=85):
        self.id = obs_id
        self.x = float(x)
        self.y = float(y)
        self.width = width
        self.height = height
        self.vx = vx
        self.vy = vy
        self.lane_type = lane_type  # 'horizontal' or 'vertical'
        self.lead_distance = lead_distance

    @property
    def rect(self):
        return pygame.Rect(int(self.x), int(self.y), self.width, self.height)

    def get_warning_zone_rect(self):
        """
        Returns a bounding box that extends in front of the obstacle in its
        direction of movement by lead_distance, representing the Detection Area.
        """
        rx, ry, rw, rh = int(self.x), int(self.y), self.width, self.height
        pad = 8

        if self.lane_type == 'horizontal':
            if self.vx > 0:
                # Moving right: extends forward to the right
                return pygame.Rect(rx - pad, ry - pad, rw + self.lead_distance + pad, rh + pad * 2)
            else:
                # Moving left: extends forward to the left
                return pygame.Rect(rx - self.lead_distance, ry - pad, rw + self.lead_distance + pad, rh + pad * 2)
        else:
            if self.vy > 0:
                # Moving down: extends forward downwards
                return pygame.Rect(rx - pad, ry - pad, rw + pad * 2, rh + self.lead_distance + pad)
            else:
                # Moving up: extends forward upwards
                return pygame.Rect(rx - pad, ry - self.lead_distance, rw + pad * 2, rh + self.lead_distance + pad)

    def update(self):
        self.x += self.vx
        self.y += self.vy

        # Continuous looping when reaching edges
        if self.lane_type == 'horizontal':
            if self.vx > 0 and self.x > WINDOW_WIDTH + 80:
                self.x = -self.width - 70
            elif self.vx < 0 and self.x < -self.width - 80:
                self.x = WINDOW_WIDTH + 70
        else:
            if self.vy > 0 and self.y > WINDOW_HEIGHT + 80:
                self.y = -self.height - 70
            elif self.vy < 0 and self.y < -self.height - 80:
                self.y = WINDOW_HEIGHT + 70

    def draw(self, screen):
        # 1. Draw Predictive Warning Zone (Detection Area)
        w_rect = self.get_warning_zone_rect()
        w_surf = pygame.Surface((w_rect.width, w_rect.height), pygame.SRCALPHA)
        # Faint yellow transparent fill
        w_surf.fill((253, 224, 71, 75))
        # Subtle amber dashed/solid border
        pygame.draw.rect(w_surf, (245, 158, 11, 160), w_surf.get_rect(), width=2, border_radius=4)
        screen.blit(w_surf, (w_rect.x, w_rect.y))

        # 2. Draw Solid Red Obstacle
        obs_rect = self.rect
        pygame.draw.rect(screen, COLOR_OBSTACLE, obs_rect, border_radius=4)
        pygame.draw.rect(screen, COLOR_OBSTACLE_BORDER, obs_rect, width=2, border_radius=4)

        # Draw simple movement arrows inside obstacle
        cx, cy = obs_rect.centerx, obs_rect.centery
        arrow_color = (255, 255, 255)
        if self.vx > 0:
            pygame.draw.polygon(screen, arrow_color, [(cx - 6, cy - 5), (cx + 6, cy), (cx - 6, cy + 5)])
        elif self.vx < 0:
            pygame.draw.polygon(screen, arrow_color, [(cx + 6, cy - 5), (cx - 6, cy), (cx + 6, cy + 5)])
        elif self.vy > 0:
            pygame.draw.polygon(screen, arrow_color, [(cx - 5, cy - 6), (cx, cy + 6), (cx + 5, cy - 6)])
        elif self.vy < 0:
            pygame.draw.polygon(screen, arrow_color, [(cx - 5, cy + 6), (cx, cy - 6), (cx + 5, cy + 6)])


# ==========================================
# SIMULATION ENGINE
# ==========================================

class LiFiSimulation:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("Dynamic Li-Fi Beam Scheduling & Predictive Load Balancing")
        self.screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
        self.clock = pygame.time.Clock()

        # Fonts
        self.font_title = pygame.font.SysFont("Segoe UI, Arial", 18, bold=True)
        self.font_body = pygame.font.SysFont("Segoe UI, Arial", 14)
        self.font_small = pygame.font.SysFont("Segoe UI, Arial", 11, bold=True)
        self.font_tiny = pygame.font.SysFont("Segoe UI, Arial", 9, bold=True)

        # Statistics
        self.total_handovers = 0
        self.total_failures = 0
        self.extreme_congestion = False
        self.paused = False

        # Build environment components
        self.init_environment()
        self.init_network()

    def init_environment(self):
        # Predefined Lanes (Aisles between tables)
        # Horizontal Lanes across the room
        self.lane_h1 = pygame.Rect(0, 260, WINDOW_WIDTH, 60)
        self.lane_h2 = pygame.Rect(0, 680, WINDOW_WIDTH, 60)
        # Vertical Lanes across the room
        self.lane_v1 = pygame.Rect(320, 0, 60, WINDOW_HEIGHT)
        self.lane_v2 = pygame.Rect(620, 0, 60, WINDOW_HEIGHT)
        self.lanes = [self.lane_h1, self.lane_h2, self.lane_v1, self.lane_v2]

        # 5 Library Study Tables
        self.tables = [
            Table(0, pygame.Rect(120, 390, 160, 80), "Table 1 (NW)"),
            Table(1, pygame.Rect(720, 390, 160, 80), "Table 2 (NE)"),
            Table(2, pygame.Rect(420, 460, 160, 80), "Table 3 (Center Hub)"),
            Table(3, pygame.Rect(120, 530, 160, 80), "Table 4 (SW)"),
            Table(4, pygame.Rect(720, 530, 160, 80), "Table 5 (SE)"),
        ]

        # Obstacles moving along horizontal and vertical lanes
        self.obstacles = [
            # Lane H1 (Y=260-320): Obstacles traversing East/West
            Obstacle(1, 100, 273, 46, 34, vx=2.2, vy=0, lane_type='horizontal', lead_distance=85),
            Obstacle(2, 850, 273, 46, 34, vx=-2.4, vy=0, lane_type='horizontal', lead_distance=90),
            
            # Lane H2 (Y=680-740): Obstacles traversing East/West
            Obstacle(3, 800, 693, 46, 34, vx=-2.0, vy=0, lane_type='horizontal', lead_distance=85),
            Obstacle(4, 180, 693, 46, 34, vx=2.3, vy=0, lane_type='horizontal', lead_distance=90),

            # Lane V1 (X=320-380): Obstacle traversing South
            Obstacle(5, 333, 120, 34, 46, vx=0, vy=2.1, lane_type='vertical', lead_distance=85),

            # Lane V2 (X=620-680): Obstacle traversing North
            Obstacle(6, 633, 820, 34, 46, vx=0, vy=-2.2, lane_type='vertical', lead_distance=85),
        ]

    def init_network(self):
        # 6 Access Points placed evenly in a 3x2 grid across the library ceiling
        # Row 1 (top): Y = 130
        # Row 2 (bottom): Y = 870
        self.aps = [
            AccessPoint(0, 200, 130),
            AccessPoint(1, 500, 130),
            AccessPoint(2, 800, 130),
            AccessPoint(3, 200, 870),
            AccessPoint(4, 500, 870),
            AccessPoint(5, 800, 870),
        ]

        # Stationary Library Users clustered around the tables
        # Generating 26 users to deliberately trigger load balancing (6 APs * 5 capacity = 30 max capacity)
        self.users = []
        user_id = 1

        table_user_offsets = [
            # 5 users at Table 1
            [(-55, -20), (0, -22), (55, -20), (-35, 20), (35, 20)],
            # 5 users at Table 2
            [(-55, -20), (0, -22), (55, -20), (-35, 20), (35, 20)],
            # 6 users at Table 3 (Center Hub)
            [(-55, -22), (0, -24), (55, -22), (-55, 22), (0, 24), (55, 22)],
            # 5 users at Table 4
            [(-55, -20), (0, -22), (55, -20), (-35, 20), (35, 20)],
            # 5 users at Table 5
            [(-55, -20), (0, -22), (55, -20), (-35, 20), (35, 20)],
        ]

        for t_idx, table in enumerate(self.tables):
            cx, cy = table.rect.center
            for dx, dy in table_user_offsets[t_idx]:
                ux = cx + dx
                uy = cy + dy
                self.users.append(User(user_id, ux, uy, table.id))
                user_id += 1

        # Perform initial association
        self.initial_beam_association()

    def initial_beam_association(self):
        """Initial connection: associate each user with the closest available AP."""
        for user in self.users:
            sorted_aps = sorted(self.aps, key=lambda ap: ap.distance_to(user.pos))
            for ap in sorted_aps:
                if not ap.is_full:
                    # Check clear line of sight
                    if not self.is_path_threatened(user.pos, ap.pos) and not self.is_path_blocked(user.pos, ap.pos):
                        user.current_ap = ap
                        ap.connected_users.append(user)
                        break
            if user.current_ap is None:
                # Fallback to nearest with capacity
                for ap in sorted_aps:
                    if not ap.is_full:
                        user.current_ap = ap
                        ap.connected_users.append(user)
                        break

    # ==========================================
    # LINE OF SIGHT (LoS) CHECKING VIA CLIPLINE
    # ==========================================
    def is_path_blocked(self, p1, p2):
        """Checks if solid red obstacle physically intersects line segment p1-p2."""
        for obs in self.obstacles:
            if bool(obs.rect.clipline(p1, p2)):
                return True
        return False

    def is_path_threatened(self, p1, p2):
        """Checks if predictive warning zone intersects line segment p1-p2."""
        for obs in self.obstacles:
            if bool(obs.get_warning_zone_rect().clipline(p1, p2)):
                return True
        return False

    # ==========================================
    # PROACTIVE BEAM SCHEDULING & LOAD BALANCING
    # ==========================================
    def update_beam_scheduling(self):
        """
        Continuously evaluates LoS for all users:
        1. Proactive Handover: Triggered BEFORE physical blockage when warning zone is breached.
        2. Visualizes threat via thick Orange line, then assigns candidate AP with thick Green beam.
        3. Load Balancing: Cascades to next closest AP if nearest is at full capacity.
        4. Total Network/Physical Failure: Drops to Red line ONLY if all options are full or blocked.
        """
        for user in self.users:
            # Decrement threat visualization timer
            if user.threat_timer > 0:
                user.threat_timer -= 1
                if user.threat_timer == 0:
                    user.threatened_ap = None

            # Decrement handover hysteresis cooldown
            if user.handover_cooldown > 0:
                user.handover_cooldown -= 1

            current_ap = user.current_ap

            # Case A: User currently has an active AP
            if current_ap is not None:
                active_threatened = self.is_path_threatened(user.pos, current_ap.pos)
                active_blocked = self.is_path_blocked(user.pos, current_ap.pos)

                # Trigger handover if physically blocked OR if threatened and cooldown elapsed
                if active_blocked or (active_threatened and user.handover_cooldown == 0):
                    # Imminent Blockage Registered!
                    # Temporarily save threatened AP to draw thick ORANGE line
                    user.threatened_ap = current_ap
                    user.threat_timer = THREAT_FLASH_FRAMES

                    # Execute Handover
                    handover_target = self.find_handover_candidate(user, exclude_ap=current_ap)

                    if handover_target is not None:
                        # Successful Proactive Handover!
                        old_ap_id = current_ap.id + 1
                        new_ap_id = handover_target.id + 1

                        current_ap.connected_users.remove(user)
                        handover_target.connected_users.append(user)
                        user.current_ap = handover_target
                        user.failed_ap = None
                        user.is_dropped = False
                        user.handover_cooldown = HANDOVER_COOLDOWN_FRAMES
                        self.total_handovers += 1

                        print(f"[PROACTIVE HANDOVER] User #{user.id:02d} handed over: AP-{old_ap_id} -> AP-{new_ap_id} "
                              f"| Target Load: {handover_target.load}/{handover_target.max_capacity} "
                              f"| Reason: Imminent Blockage Detected in Warning Zone")
                    else:
                        # Edge Case: Proactive Handover Failed!
                        # Occurs IF AND ONLY IF all alternative APs are at max capacity OR blocked.
                        if active_blocked:
                            # Total Physical Failure limit reached: connection drops!
                            current_ap.connected_users.remove(user)
                            user.failed_ap = current_ap
                            user.current_ap = None
                            user.is_dropped = True
                            self.total_failures += 1
                            print(f"[PHYSICAL FAILURE] User #{user.id:02d} connection DROPPED! "
                                  f"All alternative APs at maximum capacity ({AP_MAX_CAPACITY}) or paths occluded.")
                        else:
                            # Beam is threatened by warning zone, but not yet physically blocked.
                            # Keep holding connection until actual blockage occurs or slot opens.
                            pass

            # Case B: User currently disconnected (Red State recovery)
            else:
                recovery_target = self.find_handover_candidate(user, exclude_ap=None)
                if recovery_target is not None:
                    recovery_target.connected_users.append(user)
                    user.current_ap = recovery_target
                    user.is_dropped = False
                    user.failed_ap = None
                    print(f"[CONNECTION RESTORED] User #{user.id:02d} recovered connection to AP-{recovery_target.id + 1} "
                          f"| Load: {recovery_target.load}/{recovery_target.max_capacity}")

    def find_handover_candidate(self, user, exclude_ap=None):
        """
        Finds the optimal candidate AP for handover:
        1. Must NOT be the excluded AP.
        2. Must have a completely clear LoS (neither warning zone nor solid obstacle).
        3. Must NOT be overloaded (load < max_capacity).
        4. Sorted by nearest Euclidean distance.
        """
        candidates = []
        for ap in self.aps:
            if exclude_ap is not None and ap == exclude_ap:
                continue
            if ap.is_full:
                continue  # Load Balancing rule: skip full APs
            
            # Check completely clear LoS
            if not self.is_path_threatened(user.pos, ap.pos) and not self.is_path_blocked(user.pos, ap.pos):
                dist = ap.distance_to(user.pos)
                candidates.append((dist, ap))

        if candidates:
            # Sort by distance (next nearest available AP)
            candidates.sort(key=lambda item: item[0])
            return candidates[0][1]

        # Secondary fallback: if no completely unthreatened AP is available,
        # can an AP with clear physical LoS (even if near warning zone boundary) accept user?
        secondary_candidates = []
        for ap in self.aps:
            if exclude_ap is not None and ap == exclude_ap:
                continue
            if ap.is_full:
                continue
            if not self.is_path_blocked(user.pos, ap.pos):
                secondary_candidates.append((ap.distance_to(user.pos), ap))

        if secondary_candidates:
            secondary_candidates.sort(key=lambda item: item[0])
            return secondary_candidates[0][1]

        return None

    def toggle_extreme_congestion(self):
        """Toggles extreme congestion mode by modifying obstacle density and AP capacity."""
        self.extreme_congestion = not self.extreme_congestion
        if self.extreme_congestion:
            print("\n[MODE] >>> EXTREME CONGESTION MODE ACTIVATED <<<")
            print("[MODE] AP capacity tightened to 4 users; extra cross-obstacles deployed.")
            for ap in self.aps:
                ap.max_capacity = 4
            # Add extra dense obstacles
            self.obstacles.append(Obstacle(99, 450, 480, 50, 36, vx=3.0, vy=0, lane_type='horizontal', lead_distance=95))
            self.obstacles.append(Obstacle(100, 500, 300, 36, 50, vx=0, vy=3.0, lane_type='vertical', lead_distance=95))
        else:
            print("\n[MODE] Normal Operation Restored.")
            for ap in self.aps:
                ap.max_capacity = AP_MAX_CAPACITY
            self.obstacles = [o for o in self.obstacles if o.id < 90]

    # ==========================================
    # RENDERING & VISUALIZATION
    # ==========================================
    def draw_environment(self):
        # Background
        self.screen.fill(BG_COLOR)

        # Subtle floor grid
        grid_step = 50
        for gx in range(0, WINDOW_WIDTH, grid_step):
            pygame.draw.line(self.screen, FLOOR_TILE_COLOR, (gx, 0), (gx, WINDOW_HEIGHT), 1)
        for gy in range(0, WINDOW_HEIGHT, grid_step):
            pygame.draw.line(self.screen, FLOOR_TILE_COLOR, (0, gy), (WINDOW_WIDTH, gy), 1)

        # Draw Lanes (walkways / aisles between tables)
        for lane in self.lanes:
            pygame.draw.rect(self.screen, LANE_COLOR, lane)
            pygame.draw.rect(self.screen, LANE_BORDER_COLOR, lane, width=1)
            # Dashed lane centerline
            if lane.width > lane.height:
                # Horizontal lane
                cy = lane.centery
                for dash_x in range(0, WINDOW_WIDTH, 30):
                    pygame.draw.line(self.screen, LANE_BORDER_COLOR, (dash_x, cy), (dash_x + 15, cy), 1)
            else:
                # Vertical lane
                cx = lane.centerx
                for dash_y in range(0, WINDOW_HEIGHT, 30):
                    pygame.draw.line(self.screen, LANE_BORDER_COLOR, (cx, dash_y), (cx, dash_y + 15), 1)

        # Draw Tables
        for table in self.tables:
            table.draw(self.screen, self.font_small)

    def draw_lifi_beams(self):
        """
        Draws Li-Fi beams according to protocol state:
        - Thick ORANGE line: Threat detected / warning zone breached.
        - Thick GREEN line: Active high-speed connection.
        - Thin RED line: Dropped connection / network limit reached.
        """
        # 1. Draw Thick ORANGE lines for active threat handovers
        for user in self.users:
            if user.threat_timer > 0 and user.threatened_ap is not None:
                pygame.draw.line(self.screen, COLOR_THREAT_BEAM, user.threatened_ap.pos, user.pos, width=5)

        # 2. Draw Thick GREEN lines for active high-speed connections
        for user in self.users:
            if user.current_ap is not None:
                pygame.draw.line(self.screen, COLOR_ACTIVE_BEAM, user.current_ap.pos, user.pos, width=4)

        # 3. Draw Thin RED lines for dropped connections (physical failure limit)
        for user in self.users:
            if user.is_dropped and user.failed_ap is not None:
                pygame.draw.line(self.screen, COLOR_BLOCKED_BEAM, user.failed_ap.pos, user.pos, width=2)

    def draw_hud(self):
        """Renders real-time metrics, AP load indicators, and color legend."""
        # Top HUD Banner
        banner_rect = pygame.Rect(15, 12, WINDOW_WIDTH - 30, 48)
        banner_surf = pygame.Surface((banner_rect.width, banner_rect.height), pygame.SRCALPHA)
        banner_surf.fill((255, 255, 255, 225))
        pygame.draw.rect(banner_surf, (203, 213, 225), banner_surf.get_rect(), width=1, border_radius=8)
        self.screen.blit(banner_surf, (banner_rect.x, banner_rect.y))

        title = self.font_title.render("DYNAMIC LI-FI BEAM SCHEDULING SIMULATION", True, TEXT_MAIN_COLOR)
        self.screen.blit(title, (banner_rect.x + 15, banner_rect.y + 6))

        stats_str = f"Handovers: {self.total_handovers}  |  Physical Drops: {self.total_failures}  |  Users: {len(self.users)}  |  Mode: {'EXTREME CONGESTION [C]' if self.extreme_congestion else 'Standard [C]'}"
        stats_surf = self.font_body.render(stats_str, True, (220, 38, 38) if self.extreme_congestion else TEXT_MUTED_COLOR)
        self.screen.blit(stats_surf, (banner_rect.x + 15, banner_rect.y + 26))

        # Bottom Information & Legend Card
        legend_rect = pygame.Rect(15, WINDOW_HEIGHT - 65, WINDOW_WIDTH - 30, 52)
        legend_surf = pygame.Surface((legend_rect.width, legend_rect.height), pygame.SRCALPHA)
        legend_surf.fill((255, 255, 255, 230))
        pygame.draw.rect(legend_surf, (203, 213, 225), legend_surf.get_rect(), width=1, border_radius=8)
        self.screen.blit(legend_surf, (legend_rect.x, legend_rect.y))

        # Legend items
        items = [
            (COLOR_AP, "AP (Cap: 5)"),
            (COLOR_USER, "Static User"),
            (COLOR_ACTIVE_BEAM, "Active Beam (Green)"),
            (COLOR_THREAT_BEAM, "Threat Handover (Orange)"),
            (COLOR_BLOCKED_BEAM, "Physical Failure (Red)"),
            (COLOR_OBSTACLE, "Solid Obstacle"),
            ((245, 158, 11), "Warning Zone"),
        ]

        start_x = legend_rect.x + 20
        y_pos = legend_rect.y + 14
        for color, label in items:
            if "Beam" in label or "Failure" in label:
                pygame.draw.line(self.screen, color, (start_x, y_pos + 6), (start_x + 22, y_pos + 6), width=4 if "Active" in label or "Threat" in label else 2)
            elif "Warning" in label:
                warn_s = pygame.Surface((18, 12), pygame.SRCALPHA)
                warn_s.fill((253, 224, 71, 120))
                pygame.draw.rect(warn_s, (245, 158, 11), warn_s.get_rect(), width=1)
                self.screen.blit(warn_s, (start_x, y_pos))
            elif "Obstacle" in label:
                pygame.draw.rect(self.screen, color, (start_x, y_pos, 18, 12), border_radius=2)
            else:
                pygame.draw.circle(self.screen, color, (start_x + 8, y_pos + 6), 6)

            txt = self.font_small.render(label, True, TEXT_MAIN_COLOR)
            self.screen.blit(txt, (start_x + 26, y_pos))
            start_x += txt.get_width() + 45

        # Key commands instruction
        cmd_txt = self.font_tiny.render("[SPACE]: Pause  |  [C]: Toggle Extreme Congestion Edge-Case  |  [ESC]: Quit", True, TEXT_MUTED_COLOR)
        self.screen.blit(cmd_txt, (legend_rect.x + 20, legend_rect.y + 34))

    # ==========================================
    # MAIN LOOP
    # ==========================================
    def run(self):
        print("=" * 70)
        print("  DYNAMIC LI-FI BEAM SCHEDULING SIMULATION INITIALIZED")
        print("  - 6 Ceiling Access Points (Capacity: 5 users/AP)")
        print("  - 26 Clustered Static Library Users across 5 Study Tables")
        print("  - Predictive Warning Zones tracking imminent obstacles")
        print("  - Proactive Handover: Orange detection line -> Green handover")
        print("  - Cascading Load Balancing when candidate AP is full")
        print("  - Extreme Congestion Fallback: Thin Red line failure state")
        print("  - Controls: Press [C] to toggle Extreme Congestion, [SPACE] to pause")
        print("=" * 70)

        running = True
        while running:
            self.clock.tick(FPS)

            # Event Handling
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        running = False
                    elif event.key == pygame.K_SPACE:
                        self.paused = not self.paused
                        print(f"[STATUS] Simulation {'PAUSED' if self.paused else 'RESUMED'}")
                    elif event.key == pygame.K_c:
                        self.toggle_extreme_congestion()

            if not self.paused:
                # Update Obstacle positions in predefined lanes
                for obs in self.obstacles:
                    obs.update()

                # Core Logic: LoS tracking, Warning Zone detection, Handover & Load Balancing
                self.update_beam_scheduling()

            # Render Scene
            self.draw_environment()
            self.draw_lifi_beams()

            # Draw Obstacles & Warning Zones
            for obs in self.obstacles:
                obs.draw(self.screen)

            # Draw Users
            for user in self.users:
                user.draw(self.screen, self.font_tiny)

            # Draw APs
            for ap in self.aps:
                ap.draw(self.screen, self.font_small)

            # Draw HUD Overlay
            self.draw_hud()

            pygame.display.flip()

        pygame.quit()
        print("\n[SIMULATION TERMINATED] Window closed.")


if __name__ == "__main__":
    simulation = LiFiSimulation()
    simulation.run()
