/**
 * LuminaLanes — Dynamic Li-Fi Beam Scheduling & Load Balancing Digital Twin
 * Main Application Engine
 * 
 * Architecture:
 * 1. Geometry & Intersection Utilities (Line-Rect, Line-Polygon, Raycasting)
 * 2. Entity Model: AccessPoint, User, Table, StationaryObstacle, MovingObstacle, BeamParticle
 * 3. Core Simulation Controller (LiFiDigitalTwin):
 *    - Tri-State Beam Handover FSM (Active Green, Threat Orange, Blocked Red)
 *    - Cascading Capacity Load Balancer (Max 3 users/AP default)
 *    - High-DPI 60 FPS HTML5 Canvas Renderer
 * 4. UI Manager: View Switcher (Home, Load Balancing, Predictive Sensing),
 *    Controls Toolbar, Interactive Tooltip Inspector, Real-time Event Logger, Audio Synth.
 */

// ============================================================================
// 1. GEOMETRY & VECTOR UTILITIES
// ============================================================================

const MathUtils = {
  distance(p1, p2) {
    return Math.hypot(p1.x - p2.x, p1.y - p2.y);
  },

  // Check if line segment AB intersects line segment CD
  lineIntersectsLine(p1, p2, p3, p4) {
    const denom = (p4.y - p3.y) * (p2.x - p1.x) - (p4.x - p3.x) * (p2.y - p1.y);
    if (denom === 0) return false;

    const ua = ((p4.x - p3.x) * (p1.y - p3.y) - (p4.y - p3.y) * (p1.x - p3.x)) / denom;
    const ub = ((p2.x - p1.x) * (p1.y - p3.y) - (p2.y - p1.y) * (p1.x - p3.x)) / denom;

    return ua >= 0 && ua <= 1 && ub >= 0 && ub <= 1;
  },

  // Check if a point is inside a rectangle
  pointInRect(pt, rect) {
    return pt.x >= rect.x && pt.x <= rect.x + rect.w &&
           pt.y >= rect.y && pt.y <= rect.y + rect.h;
  },

  // Check if a point is inside an arbitrary polygon (ray casting)
  pointInPolygon(pt, vertices) {
    let inside = false;
    for (let i = 0, j = vertices.length - 1; i < vertices.length; j = i++) {
      const xi = vertices[i].x, yi = vertices[i].y;
      const xj = vertices[j].x, yj = vertices[j].y;
      const intersect = ((yi > pt.y) !== (yj > pt.y)) &&
                        (pt.x < (xj - xi) * (pt.y - yi) / (yj - yi) + xi);
      if (intersect) inside = !inside;
    }
    return inside;
  },

  // Check if line segment intersects a rectangle (either intersects edges or ends inside)
  lineIntersectsRect(p1, p2, rect) {
    if (this.pointInRect(p1, rect) || this.pointInRect(p2, rect)) return true;

    const rTopLeft = { x: rect.x, y: rect.y };
    const rTopRight = { x: rect.x + rect.w, y: rect.y };
    const rBottomRight = { x: rect.x + rect.w, y: rect.y + rect.h };
    const rBottomLeft = { x: rect.x, y: rect.y + rect.h };

    return this.lineIntersectsLine(p1, p2, rTopLeft, rTopRight) ||
           this.lineIntersectsLine(p1, p2, rTopRight, rBottomRight) ||
           this.lineIntersectsLine(p1, p2, rBottomRight, rBottomLeft) ||
           this.lineIntersectsLine(p1, p2, rBottomLeft, rTopLeft);
  },

  // Check if line segment intersects an arbitrary polygon
  lineIntersectsPolygon(p1, p2, vertices) {
    if (this.pointInPolygon(p1, vertices) || this.pointInPolygon(p2, vertices)) return true;

    for (let i = 0; i < vertices.length; i++) {
      const v1 = vertices[i];
      const v2 = vertices[(i + 1) % vertices.length];
      if (this.lineIntersectsLine(p1, p2, v1, v2)) return true;
    }
    return false;
  }
};

// ============================================================================
// 2. AUDIO FEEDBACK (SYNTHESIZED OPTICAL CHIMES)
// ============================================================================

class AudioEngine {
  constructor() {
    this.ctx = null;
    this.enabled = true;
  }

  init() {
    if (!this.ctx) {
      const AudioCtx = window.AudioContext || window.webkitAudioContext;
      if (AudioCtx) {
        this.ctx = new AudioCtx();
      }
    }
  }

  playTone(freq, type = 'sine', duration = 0.08, gainVal = 0.04) {
    if (!this.enabled) return;
    try {
      this.init();
      if (!this.ctx || this.ctx.state === 'suspended') {
        this.ctx?.resume();
      }
      if (!this.ctx) return;

      const osc = this.ctx.createOscillator();
      const gain = this.ctx.createGain();

      osc.type = type;
      osc.frequency.setValueAtTime(freq, this.ctx.currentTime);
      gain.gain.setValueAtTime(gainVal, this.ctx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.0001, this.ctx.currentTime + duration);

      osc.connect(gain);
      gain.connect(this.ctx.destination);

      osc.start();
      osc.stop(this.ctx.currentTime + duration);
    } catch (e) {
      // Audio autoplay restrictions gracefully ignored
    }
  }

  playHandover() {
    this.playTone(880, 'sine', 0.1, 0.03); // High crisp ping
    setTimeout(() => this.playTone(1174.66, 'sine', 0.12, 0.025), 60);
  }

  playThreat() {
    this.playTone(440, 'triangle', 0.06, 0.02);
  }

  playDrop() {
    this.playTone(220, 'sawtooth', 0.18, 0.04);
  }
}

// ============================================================================
// 3. ENTITY MODELS
// ============================================================================

class AccessPoint {
  constructor(id, x, y, maxCapacity = 3) {
    this.id = id;
    this.x = x;
    this.y = y;
    this.pos = { x, y };
    this.maxCapacity = maxCapacity;
    this.connectedUsers = [];
    this.pulsePhase = Math.random() * Math.PI * 2;
    this.radius = 16;
  }

  get load() {
    return this.connectedUsers.length;
  }

  get isFull() {
    return this.load >= this.maxCapacity;
  }

  distanceTo(pos) {
    return MathUtils.distance(this.pos, pos);
  }
}

class User {
  constructor(id, x, y, tableId) {
    this.id = id;
    this.x = x;
    this.y = y;
    this.pos = { x, y };
    this.tableId = tableId;

    this.currentAp = null;
    this.threatenedAp = null;
    this.threatTimer = 0;
    this.failedAp = null;
    this.isDropped = false;
    this.handoverCooldown = 0;

    // Transition interpolation for smooth visual fade
    this.previousAp = null;
    this.fadeProgress = 1.0;
  }
}

class Table {
  constructor(id, x, y, w, h, name) {
    this.id = id;
    this.x = x;
    this.y = y;
    this.w = w;
    this.h = h;
    this.rect = { x, y, w, h };
    this.name = name;
  }
}

class StationaryObstacle {
  constructor(id, x, y, w, h, type = 'bookshelf', label = '') {
    this.id = id;
    this.x = x;
    this.y = y;
    this.w = w;
    this.h = h;
    this.rect = { x, y, w, h };
    this.type = type; // 'bookshelf' or 'pillar'
    this.label = label;
  }
}

class MovingObstacle {
  constructor(id, x, y, w, h, vx, vy, laneType, leadDistance = 90) {
    this.id = id;
    this.x = x;
    this.y = y;
    this.w = w;
    this.h = h;
    this.vx = vx;
    this.vy = vy;
    this.baseVx = vx;
    this.baseVy = vy;
    this.laneType = laneType; // 'horizontal' or 'vertical'
    this.leadDistance = leadDistance;
  }

  get rect() {
    return { x: this.x, y: this.y, w: this.w, h: this.h };
  }

  // Direction angle in radians
  get heading() {
    return Math.atan2(this.vy, this.vx);
  }

  // Returns polygonal vertices of the forward-projecting Warning Zone
  getWarningZonePolygon() {
    const cx = this.x + this.w / 2;
    const cy = this.y + this.h / 2;
    const angle = this.heading;
    const forwardDist = this.leadDistance;
    const halfWidth = (this.laneType === 'horizontal' ? this.h : this.w) * 0.9;
    const tipWidth = halfWidth * 1.4; // Slightly expanding detection cone

    const cosA = Math.cos(angle);
    const sinA = Math.sin(angle);
    const perpCos = -sinA;
    const perpSin = cosA;

    // Base left and right
    const b1 = { x: cx + perpCos * halfWidth, y: cy + perpSin * halfWidth };
    const b2 = { x: cx - perpCos * halfWidth, y: cy - perpSin * halfWidth };

    // Forward tip left and right
    const t1 = {
      x: cx + cosA * forwardDist + perpCos * tipWidth,
      y: cy + sinA * forwardDist + perpSin * tipWidth
    };
    const t2 = {
      x: cx + cosA * forwardDist - perpCos * tipWidth,
      y: cy + sinA * forwardDist - perpSin * tipWidth
    };

    return [b1, t1, t2, b2];
  }

  update(speedFactor, canvasW = 1000, canvasH = 800) {
    this.x += this.vx * speedFactor;
    this.y += this.vy * speedFactor;

    // Continuous smooth looping across canvas boundaries
    if (this.laneType === 'horizontal') {
      if (this.vx > 0 && this.x > canvasW + 60) {
        this.x = -this.w - 50;
      } else if (this.vx < 0 && this.x < -this.w - 60) {
        this.x = canvasW + 50;
      }
    } else {
      if (this.vy > 0 && this.y > canvasH + 60) {
        this.y = -this.h - 50;
      } else if (this.vy < 0 && this.y < -this.h - 60) {
        this.y = canvasH + 50;
      }
    }
  }
}

// Photon particle for "Animated Pulse" laser mode
class BeamParticle {
  constructor(startX, startY, endX, endY, color, speed) {
    this.startX = startX;
    this.startY = startY;
    this.endX = endX;
    this.endY = endY;
    this.color = color;
    this.progress = Math.random();
    this.speed = speed;
  }

  update() {
    this.progress += this.speed;
    if (this.progress > 1) {
      this.progress = 0;
    }
  }

  get pos() {
    return {
      x: this.startX + (this.endX - this.startX) * this.progress,
      y: this.startY + (this.endY - this.startY) * this.progress
    };
  }
}

// ============================================================================
// 4. CORE DIGITAL TWIN SIMULATION ENGINE
// ============================================================================

class LiFiDigitalTwin {
  constructor() {
    this.canvas = document.getElementById('simCanvas');
    this.ctx = this.canvas.getContext('2d');
    this.audio = new AudioEngine();

    // Native resolution
    this.nativeWidth = 1000;
    this.nativeHeight = 800;

    // Modes & Configuration
    this.activeSolution = 'load-balance'; // 'load-balance' or 'predictive'
    this.isPaused = false;
    this.speedMultiplier = 1.0;
    this.defaultCapacity = 3; // Default 3 users/AP
    this.beamStyle = 'pulse'; // 'pulse', 'fade', 'instant'
    this.showGrid = true;
    this.showZones = true;
    this.reactiveModeOnly = false; // Page 2 comparison toggle

    // Telemetry Statistics
    this.stats = {
      proactiveHandovers: 0,
      loadRedirects: 0,
      physicalDrops: 0,
      totalHandovers: 0,
      simTimeSeconds: 0
    };

    // FPS & Timers
    this.lastFrameTime = performance.now();
    this.fps = 60;
    this.frameCount = 0;

    // Optical Photon Particles
    this.particles = [];

    // Hover Inspection Tooltip state
    this.mousePos = { x: -100, y: -100 };
    this.hoveredEntity = null;

    // Initialize Layout & Network
    this.initEnvironment();
    this.initNetwork();
    this.setupCanvasDPI();

    // Event Listeners
    this.bindEvents();

    // Start Simulation Loop
    requestAnimationFrame((t) => this.loop(t));
  }

  setupCanvasDPI() {
    const dpr = window.devicePixelRatio || 1;
    this.canvas.width = this.nativeWidth * dpr;
    this.canvas.height = this.nativeHeight * dpr;
    this.ctx.scale(dpr, dpr);
  }

  initEnvironment() {
    // 4 Walkway Lanes (Aisles between tables)
    this.lanes = [
      { id: 'h1', x: 0, y: 220, w: this.nativeWidth, h: 60, type: 'horizontal' },
      { id: 'h2', x: 0, y: 550, w: this.nativeWidth, h: 60, type: 'horizontal' },
      { id: 'v1', x: 270, y: 0, w: 60, h: this.nativeHeight, type: 'vertical' },
      { id: 'v2', x: 670, y: 0, w: 60, h: this.nativeHeight, type: 'vertical' }
    ];

    // 5 Library Study Tables
    this.tables = [
      new Table(1, 100, 330, 140, 75, 'Table 1 (NW Zone)'),
      new Table(2, 760, 330, 140, 75, 'Table 2 (NE Zone)'),
      new Table(3, 400, 380, 200, 90, 'Table 3 (Center Hub)'),
      new Table(4, 100, 440, 140, 75, 'Table 4 (SW Zone)'),
      new Table(5, 760, 440, 140, 75, 'Table 5 (SE Zone)')
    ];

    // Stationary Obstacles (Permanent infrastructure: Bookshelves & Concrete Pillars)
    this.stationaryObstacles = [
      // Tall perimeter bookshelves (solid optical shadows)
      new StationaryObstacle(1, 20, 330, 50, 190, 'bookshelf', 'Stacks NW'),
      new StationaryObstacle(2, 930, 330, 50, 190, 'bookshelf', 'Stacks NE'),
      new StationaryObstacle(3, 410, 20, 180, 45, 'bookshelf', 'Reference Section'),
      new StationaryObstacle(4, 410, 735, 180, 45, 'bookshelf', 'Periodicals'),
      // Central structural pillars
      new StationaryObstacle(5, 275, 395, 50, 45, 'pillar', 'Pillar A'),
      new StationaryObstacle(6, 675, 395, 50, 45, 'pillar', 'Pillar B')
    ];

    // Moving Obstacles (Patrons walking along aisles with forward warning zones)
    this.initObstacles();
  }

  initObstacles() {
    this.obstacles = [
      // Lane H1 (Y=220): Moving West -> East
      new MovingObstacle(1, 60, 235, 32, 30, 1.8, 0, 'horizontal', 85),
      // Lane H1 (Y=220): Moving East -> West
      new MovingObstacle(2, 860, 235, 32, 30, -1.9, 0, 'horizontal', 90),

      // Lane H2 (Y=550): Moving West -> East
      new MovingObstacle(3, 150, 565, 32, 30, 2.0, 0, 'horizontal', 85),
      // Lane H2 (Y=550): Moving East -> West
      new MovingObstacle(4, 800, 565, 32, 30, -1.7, 0, 'horizontal', 90),

      // Lane V1 (X=270): Moving North -> South
      new MovingObstacle(5, 285, 90, 30, 32, 0, 1.9, 'vertical', 85),

      // Lane V2 (X=670): Moving South -> North
      new MovingObstacle(6, 685, 680, 30, 32, 0, -2.0, 'vertical', 85)
    ];
  }

  initNetwork() {
    // 6 Ceiling Access Points placed in a 3x2 matrix
    // Row 1: Y = 110
    // Row 2: Y = 690
    this.aps = [
      new AccessPoint(0, 180, 110, this.defaultCapacity),
      new AccessPoint(1, 500, 110, this.defaultCapacity),
      new AccessPoint(2, 820, 110, this.defaultCapacity),
      new AccessPoint(3, 180, 690, this.defaultCapacity),
      new AccessPoint(4, 500, 690, this.defaultCapacity),
      new AccessPoint(5, 820, 690, this.defaultCapacity)
    ];

    // 26 Static Library Users clustered around the 5 tables
    this.users = [];
    let userId = 1;

    const tableUserOffsets = [
      // 5 users at Table 1 (NW)
      [[-45, -18], [0, -20], [45, -18], [-30, 18], [30, 18]],
      // 5 users at Table 2 (NE)
      [[-45, -18], [0, -20], [45, -18], [-30, 18], [30, 18]],
      // 6 users at Table 3 (Center Hub)
      [[-60, -22], [0, -24], [60, -22], [-60, 22], [0, 24], [60, 22]],
      // 5 users at Table 4 (SW)
      [[-45, -18], [0, -20], [45, -18], [-30, 18], [30, 18]],
      // 5 users at Table 5 (SE)
      [[-45, -18], [0, -20], [45, -18], [-30, 18], [30, 18]]
    ];

    this.tables.forEach((table, tIdx) => {
      const cx = table.x + table.w / 2;
      const cy = table.y + table.h / 2;
      tableUserOffsets[tIdx].forEach(([dx, dy]) => {
        this.users.push(new User(userId++, cx + dx, cy + dy, table.id));
      });
    });

    // Perform initial association
    this.performInitialAssociation();
  }

  performInitialAssociation() {
    // Clear existing AP connections
    this.aps.forEach(ap => ap.connectedUsers = []);

    // Greedily associate each user with closest AP that is not full and has clear LoS
    this.users.forEach(user => {
      const sortedAps = [...this.aps].sort((a, b) => a.distanceTo(user.pos) - b.distanceTo(user.pos));
      let assigned = false;

      for (const ap of sortedAps) {
        if (!ap.isFull && !this.isPathBlocked(user.pos, ap.pos) && !this.isPathThreatened(user.pos, ap.pos)) {
          user.currentAp = ap;
          ap.connectedUsers.push(user);
          assigned = true;
          break;
        }
      }

      // Fallback: assign to nearest available with physical LoS
      if (!assigned) {
        for (const ap of sortedAps) {
          if (!ap.isFull && !this.isPathBlocked(user.pos, ap.pos)) {
            user.currentAp = ap;
            ap.connectedUsers.push(user);
            assigned = true;
            break;
          }
        }
      }

      // Edge case: total saturation fallback
      if (!assigned) {
        for (const ap of sortedAps) {
          if (!ap.isFull) {
            user.currentAp = ap;
            ap.connectedUsers.push(user);
            assigned = true;
            break;
          }
        }
      }
    });
  }

  // ==========================================================================
  // RAYCAST & COLLISION DETECTION
  // ==========================================================================

  isPathBlocked(p1, p2) {
    // 1. Check against stationary bookshelves and pillars
    for (const obs of this.stationaryObstacles) {
      if (MathUtils.lineIntersectsRect(p1, p2, obs.rect)) return true;
    }

    // 2. Check against solid physical bodies of moving obstacles
    for (const obs of this.obstacles) {
      if (MathUtils.lineIntersectsRect(p1, p2, obs.rect)) return true;
    }

    return false;
  }

  isPathThreatened(p1, p2) {
    if (!this.showZones) return false;
    for (const obs of this.obstacles) {
      const poly = obs.getWarningZonePolygon();
      if (MathUtils.lineIntersectsPolygon(p1, p2, poly)) return true;
    }
    return false;
  }

  findCandidateAp(user, excludeAp = null) {
    const candidates = [];

    for (const ap of this.aps) {
      if (excludeAp && ap === excludeAp) continue;
      if (ap.isFull) continue; // Capacity constraint

      // Strict clear path (neither warning zone nor solid obstacle)
      if (!this.isPathThreatened(user.pos, ap.pos) && !this.isPathBlocked(user.pos, ap.pos)) {
        candidates.push({ ap, dist: ap.distanceTo(user.pos) });
      }
    }

    if (candidates.length > 0) {
      candidates.sort((a, b) => a.dist - b.dist);
      return candidates[0].ap;
    }

    // Secondary fallback: unblocked physically, even if close to warning zone boundary
    const secondary = [];
    for (const ap of this.aps) {
      if (excludeAp && ap === excludeAp) continue;
      if (ap.isFull) continue;

      if (!this.isPathBlocked(user.pos, ap.pos)) {
        secondary.push({ ap, dist: ap.distanceTo(user.pos) });
      }
    }

    if (secondary.length > 0) {
      secondary.sort((a, b) => a.dist - b.dist);
      return secondary[0].ap;
    }

    return null;
  }

  // ==========================================================================
  // DYNAMIC BEAM SCHEDULING & LOAD BALANCING FSM
  // ==========================================================================

  updateBeamScheduling() {
    this.users.forEach(user => {
      if (user.threatTimer > 0) {
        user.threatTimer--;
        if (user.threatTimer === 0) {
          user.threatenedAp = null;
        }
      }

      if (user.handoverCooldown > 0) {
        user.handoverCooldown--;
      }

      // Smooth transition progress
      if (user.fadeProgress < 1.0) {
        user.fadeProgress = Math.min(1.0, user.fadeProgress + 0.05);
      }

      const currentAp = user.currentAp;

      if (currentAp !== null) {
        const isThreatened = this.isPathThreatened(user.pos, currentAp.pos);
        const isBlocked = this.isPathBlocked(user.pos, currentAp.pos);

        // In Reactive Mode (comparison), handover triggers ONLY when physically blocked
        const shouldTriggerHandover = this.reactiveModeOnly
          ? isBlocked
          : (isBlocked || (isThreatened && user.handoverCooldown === 0));

        if (shouldTriggerHandover) {
          // Imminent or active threat detected!
          user.threatenedAp = currentAp;
          user.threatTimer = 25; // Render thick Orange beam for 25 frames

          const handoverTarget = this.findCandidateAp(user, currentAp);

          if (handoverTarget !== null) {
            // Proactive Handover Success!
            const oldId = currentAp.id + 1;
            const newId = handoverTarget.id + 1;

            // Shift user
            const idx = currentAp.connectedUsers.indexOf(user);
            if (idx !== -1) currentAp.connectedUsers.splice(idx, 1);
            handoverTarget.connectedUsers.push(user);

            user.previousAp = currentAp;
            user.fadeProgress = 0.0;
            user.currentAp = handoverTarget;
            user.failedAp = null;
            user.isDropped = false;
            user.handoverCooldown = 28; // Hysteresis

            this.stats.proactiveHandovers++;
            this.stats.totalHandovers++;
            this.audio.playHandover();

            this.logEvent(
              `[PROACTIVE HANDOVER] User #U${user.id} handed over: AP-${oldId} → AP-${newId} ` +
              `| Target Load: ${handoverTarget.load}/${handoverTarget.maxCapacity} ` +
              `| Reason: Imminent Warning Zone Intersect`,
              'handover-proactive'
            );
          } else {
            // No alternate candidate available!
            if (isBlocked) {
              // Physical cut without backup: beam drops!
              const idx = currentAp.connectedUsers.indexOf(user);
              if (idx !== -1) currentAp.connectedUsers.splice(idx, 1);
              user.failedAp = currentAp;
              user.currentAp = null;
              user.isDropped = true;
              this.stats.physicalDrops++;
              this.audio.playDrop();

              this.logEvent(
                `[PHYSICAL CUT] User #U${user.id} beam occluded! All candidate APs at max capacity (${this.defaultCapacity}) or blocked.`,
                'drop-failure'
              );
            }
          }
        }
      } else {
        // Disconnected user trying to recover connection
        const recoveryTarget = this.findCandidateAp(user, null);
        if (recoveryTarget !== null) {
          recoveryTarget.connectedUsers.push(user);
          user.currentAp = recoveryTarget;
          user.isDropped = false;
          user.failedAp = null;
          this.logEvent(
            `[CONNECTION RESTORED] User #U${user.id} recovered beam with AP-${recoveryTarget.id + 1} (${recoveryTarget.load}/${recoveryTarget.maxCapacity})`,
            'system-info'
          );
        }
      }
    });

    // Check for Capacity Load Balancing overflows
    this.enforceLoadBalancingLimits();
  }

  enforceLoadBalancingLimits() {
    this.aps.forEach(ap => {
      while (ap.load > ap.maxCapacity) {
        // Find furthest user to reallocate
        const excessUser = ap.connectedUsers.reduce((furthest, u) => {
          return ap.distanceTo(u.pos) > ap.distanceTo(furthest.pos) ? u : furthest;
        }, ap.connectedUsers[0]);

        const candidate = this.findCandidateAp(excessUser, ap);
        if (candidate !== null) {
          const idx = ap.connectedUsers.indexOf(excessUser);
          if (idx !== -1) ap.connectedUsers.splice(idx, 1);
          candidate.connectedUsers.push(excessUser);
          excessUser.currentAp = candidate;
          this.stats.loadRedirects++;
          this.stats.totalHandovers++;

          this.logEvent(
            `[LOAD BALANCING] AP-${ap.id + 1} capacity exceeded! Redirected User #U${excessUser.id} to AP-${candidate.id + 1} (${candidate.load}/${candidate.maxCapacity})`,
            'load-balance'
          );
        } else {
          break; // Cannot reallocate further without dropping
        }
      }
    });
  }

  // ==========================================================================
  // SCENARIO PRESETS & INTERACTIVE TRIGGERS
  // ==========================================================================

  triggerAP2Overload() {
    const ap2 = this.aps[1]; // AP-2 (Center Top)
    this.logEvent(`[BURST SIMULATION] Inducing sudden burst surge on AP-2...`, 'load-balance');
    
    // Select users from Table 3 (Center Hub) and force them into AP-2
    const hubUsers = this.users.filter(u => u.tableId === 3);
    hubUsers.forEach(u => {
      if (u.currentAp && u.currentAp !== ap2) {
        const idx = u.currentAp.connectedUsers.indexOf(u);
        if (idx !== -1) u.currentAp.connectedUsers.splice(idx, 1);
      }
      if (!ap2.connectedUsers.includes(u)) {
        ap2.connectedUsers.push(u);
        u.currentAp = ap2;
      }
    });

    // Now enforce load balancing immediately to showcase the dynamic cascade
    setTimeout(() => {
      this.enforceLoadBalancingLimits();
      this.updateUI();
    }, 400);
  }

  triggerRebalanceAll() {
    this.logEvent(`[OPTIMIZATION] Calculating optimal network load distribution across all 6 APs...`, 'system-info');
    this.performInitialAssociation();
    this.updateUI();
  }

  setCapacityLimit(newCap) {
    this.defaultCapacity = parseInt(newCap, 10);
    this.aps.forEach(ap => ap.maxCapacity = this.defaultCapacity);
    this.enforceLoadBalancingLimits();
    this.logEvent(`[CAPACITY UPDATE] Access Point capacity ceiling updated to ${newCap} users/AP.`, 'system-info');
    this.updateUI();
  }

  triggerFastCrossing() {
    const obs = this.obstacles[0];
    obs.vx = 4.2;
    this.logEvent(`[HAZARD EVENT] Accelerated Patron #1 traversing aisle at high velocity (4.2 px/frame).`, 'handover-proactive');
    setTimeout(() => { obs.vx = 1.8; }, 4000);
  }

  triggerSlowMotion() {
    this.speedMultiplier = 0.25;
    const speedSlider = document.getElementById('slider-speed');
    const speedLabel = document.getElementById('label-speed');
    if (speedSlider) speedSlider.value = 0.25;
    if (speedLabel) speedLabel.textContent = '0.25x';
    this.logEvent(`[SLOW-MOTION] Simulation scaled to 0.25x speed for frame-by-frame beam inspection.`, 'system-info');
  }

  toggleProactiveVsReactive() {
    this.reactiveModeOnly = !this.reactiveModeOnly;
    this.logEvent(
      `[MODE TOGGLE] Handover algorithm switched to: ${this.reactiveModeOnly ? 'REACTIVE (Wait for Cut)' : 'PROACTIVE (Predictive Warning Zone)'}`,
      this.reactiveModeOnly ? 'drop-failure' : 'handover-proactive'
    );
    this.updateUI();
  }

  resetSimulation() {
    this.stats.proactiveHandovers = 0;
    this.stats.loadRedirects = 0;
    this.stats.physicalDrops = 0;
    this.stats.totalHandovers = 0;
    this.stats.simTimeSeconds = 0;
    this.initObstacles();
    this.performInitialAssociation();
    this.logEvent(`[SYSTEM RESET] Entity positions and network telemetry cleared.`, 'system-info');
    this.updateUI();
  }

  stepForward() {
    if (!this.isPaused) return;
    this.updatePhysics(1.0);
    this.updateBeamScheduling();
    this.render();
    this.updateUI();
  }

  // ==========================================================================
  // RENDERING PIPELINE (60 FPS CANVAS)
  // ==========================================================================

  render() {
    const ctx = this.ctx;
    const isDark = document.documentElement.classList.contains('dark');

    ctx.clearRect(0, 0, this.nativeWidth, this.nativeHeight);

    // 1. Draw Library Floor & Grid
    this.drawFloorPlan(ctx, isDark);

    // 2. Draw Aisles & Walkways
    this.drawLanes(ctx, isDark);

    // 3. Draw Study Tables & Perimeter Bookshelves
    this.drawTablesAndShelves(ctx, isDark);

    // 4. Draw Li-Fi Optical Beams (Active Green, Threat Orange, Blocked Red)
    this.drawLiFiBeams(ctx, isDark);

    // 5. Draw Obstacles & Predictive Warning Zones
    this.drawObstacles(ctx, isDark);

    // 6. Draw Stationary Users
    this.drawUsers(ctx, isDark);

    // 7. Draw Ceiling Access Points (Pulsing blue nodes & capacity counters)
    this.drawAccessPoints(ctx, isDark);
  }

  drawFloorPlan(ctx, isDark) {
    // Floor Background
    ctx.fillStyle = isDark ? '#0b1120' : '#f8fafc';
    ctx.fillRect(0, 0, this.nativeWidth, this.nativeHeight);

    if (this.showGrid) {
      ctx.strokeStyle = isDark ? '#141d2f' : '#e2e8f0';
      ctx.lineWidth = 1;
      const step = 40;

      ctx.beginPath();
      for (let x = 0; x <= this.nativeWidth; x += step) {
        ctx.moveTo(x, 0);
        ctx.lineTo(x, this.nativeHeight);
      }
      for (let y = 0; y <= this.nativeHeight; y += step) {
        ctx.moveTo(0, y);
        ctx.lineTo(this.nativeWidth, y);
      }
      ctx.stroke();
    }
  }

  drawLanes(ctx, isDark) {
    this.lanes.forEach(lane => {
      ctx.fillStyle = isDark ? '#111827' : '#eef2f6';
      ctx.fillRect(lane.x, lane.y, lane.w, lane.h);

      ctx.strokeStyle = isDark ? '#1e293b' : '#cbd5e1';
      ctx.lineWidth = 1;
      ctx.strokeRect(lane.x, lane.y, lane.w, lane.h);

      // Dashed lane divider
      ctx.save();
      ctx.strokeStyle = isDark ? '#233249' : '#cbd5e1';
      ctx.setLineDash([8, 8]);
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      if (lane.type === 'horizontal') {
        const cy = lane.y + lane.h / 2;
        ctx.moveTo(lane.x, cy);
        ctx.lineTo(lane.x + lane.w, cy);
      } else {
        const cx = lane.x + lane.w / 2;
        ctx.moveTo(cx, lane.y);
        ctx.lineTo(cx, lane.y + lane.h);
      }
      ctx.stroke();
      ctx.restore();
    });
  }

  drawTablesAndShelves(ctx, isDark) {
    // 1. Stationary Bookshelves & Pillars
    this.stationaryObstacles.forEach(obs => {
      if (obs.type === 'bookshelf') {
        ctx.fillStyle = isDark ? '#1c1917' : '#334155';
        ctx.fillRect(obs.x, obs.y, obs.w, obs.h);
        ctx.strokeStyle = isDark ? '#44403c' : '#1e293b';
        ctx.lineWidth = 2;
        ctx.strokeRect(obs.x, obs.y, obs.w, obs.h);

        // Bookshelf internal book ridges
        ctx.fillStyle = isDark ? '#292524' : '#475569';
        const isHoriz = obs.w > obs.h;
        if (isHoriz) {
          for (let x = obs.x + 8; x < obs.x + obs.w - 8; x += 14) {
            ctx.fillRect(x, obs.y + 3, 6, obs.h - 6);
          }
        } else {
          for (let y = obs.y + 8; y < obs.y + obs.h - 8; y += 14) {
            ctx.fillRect(obs.x + 3, y, obs.w - 6, 6);
          }
        }

        // Label
        ctx.font = '10px "Inter", sans-serif';
        ctx.fillStyle = isDark ? '#a8a29e' : '#cbd5e1';
        ctx.textAlign = 'center';
        ctx.fillText(obs.label, obs.x + obs.w / 2, obs.y + obs.h / 2 + 3);
      } else {
        // Architectural Pillar
        ctx.fillStyle = isDark ? '#1e293b' : '#64748b';
        ctx.fillRect(obs.x, obs.y, obs.w, obs.h);
        ctx.strokeStyle = isDark ? '#334155' : '#475569';
        ctx.lineWidth = 2;
        ctx.strokeRect(obs.x, obs.y, obs.w, obs.h);

        ctx.font = '9px "Inter", sans-serif';
        ctx.fillStyle = '#f8fafc';
        ctx.textAlign = 'center';
        ctx.fillText('PILLAR', obs.x + obs.w / 2, obs.y + obs.h / 2 + 3);
      }
    });

    // 2. Study Tables
    this.tables.forEach(table => {
      ctx.fillStyle = isDark ? '#1a2234' : '#e2e8f0';
      ctx.fillRect(table.x, table.y, table.w, table.h);
      ctx.strokeStyle = isDark ? '#2e3d5b' : '#94a3b8';
      ctx.lineWidth = 2;
      ctx.strokeRect(table.x, table.y, table.w, table.h);

      // Table name tag
      ctx.font = '11px "Inter", sans-serif';
      ctx.fillStyle = isDark ? '#94a3b8' : '#475569';
      ctx.textAlign = 'center';
      ctx.fillText(table.name, table.x + table.w / 2, table.y + table.h / 2 + 4);
    });
  }

  drawLiFiBeams(ctx, isDark) {
    ctx.save();

    // 1. Thick Orange Pulsing Beams (Imminent Threat Handover in progress)
    this.users.forEach(user => {
      if (user.threatTimer > 0 && user.threatenedAp) {
        const pulse = 0.6 + Math.sin(Date.now() * 0.02) * 0.4;
        ctx.strokeStyle = `rgba(249, 115, 22, ${pulse})`;
        ctx.lineWidth = 5;
        ctx.shadowColor = '#f97316';
        ctx.shadowBlur = 12;

        ctx.beginPath();
        ctx.moveTo(user.threatenedAp.x, user.threatenedAp.y);
        ctx.lineTo(user.x, user.y);
        ctx.stroke();
      }
    });

    // 2. Thick Green Beams (Active High-Speed Optical Transmission)
    this.users.forEach(user => {
      if (user.currentAp) {
        let alpha = 0.85;
        if (this.beamStyle === 'fade' && user.fadeProgress < 1.0) {
          alpha = user.fadeProgress;
        }

        ctx.strokeStyle = isDark ? `rgba(74, 222, 128, ${alpha})` : `rgba(34, 197, 94, ${alpha})`;
        ctx.lineWidth = 4;
        ctx.shadowColor = '#22c55e';
        ctx.shadowBlur = isDark ? 8 : 4;

        ctx.beginPath();
        ctx.moveTo(user.currentAp.x, user.currentAp.y);
        ctx.lineTo(user.x, user.y);
        ctx.stroke();

        // Draw previous AP fading out in 'fade' mode
        if (this.beamStyle === 'fade' && user.previousAp && user.fadeProgress < 1.0) {
          const fadeOutAlpha = (1.0 - user.fadeProgress) * 0.8;
          ctx.strokeStyle = `rgba(249, 115, 22, ${fadeOutAlpha})`;
          ctx.lineWidth = 3;
          ctx.beginPath();
          ctx.moveTo(user.previousAp.x, user.previousAp.y);
          ctx.lineTo(user.x, user.y);
          ctx.stroke();
        }
      }
    });

    // 3. Thin Red Beams (Physical Failure Shadows)
    this.users.forEach(user => {
      if (user.isDropped && user.failedAp) {
        ctx.strokeStyle = '#ef4444';
        ctx.lineWidth = 2;
        ctx.shadowColor = '#ef4444';
        ctx.shadowBlur = 4;

        ctx.beginPath();
        ctx.setLineDash([4, 4]);
        ctx.moveTo(user.failedAp.x, user.failedAp.y);
        ctx.lineTo(user.x, user.y);
        ctx.stroke();
        ctx.setLineDash([]);
      }
    });

    // 4. Laser Photon Particles (if beamStyle === 'pulse')
    if (this.beamStyle === 'pulse' && !this.isPaused) {
      this.particles.forEach(p => {
        p.update();
        const pos = p.pos;
        ctx.fillStyle = p.color;
        ctx.shadowColor = p.color;
        ctx.shadowBlur = 6;
        ctx.beginPath();
        ctx.arc(pos.x, pos.y, 2.5, 0, Math.PI * 2);
        ctx.fill();
      });

      // Spawn or replenish particles
      if (this.particles.length < this.users.length * 2) {
        const u = this.users[Math.floor(Math.random() * this.users.length)];
        if (u && u.currentAp) {
          this.particles.push(new BeamParticle(u.currentAp.x, u.currentAp.y, u.x, u.y, '#ffffff', 0.02 + Math.random() * 0.02));
        }
      }
      // Prune excess
      if (this.particles.length > 80) this.particles.shift();
    }

    ctx.restore();
  }

  drawObstacles(ctx, isDark) {
    this.obstacles.forEach(obs => {
      // 1. Predictive Warning Zone (Detection Cone ahead of travel direction)
      if (this.showZones) {
        const poly = obs.getWarningZonePolygon();
        ctx.save();
        ctx.fillStyle = isDark ? 'rgba(245, 158, 11, 0.22)' : 'rgba(251, 191, 36, 0.25)';
        ctx.strokeStyle = '#f59e0b';
        ctx.lineWidth = 1.5;
        ctx.setLineDash([4, 3]);

        ctx.beginPath();
        ctx.moveTo(poly[0].x, poly[0].y);
        for (let i = 1; i < poly.length; i++) {
          ctx.lineTo(poly[i].x, poly[i].y);
        }
        ctx.closePath();
        ctx.fill();
        ctx.stroke();
        ctx.restore();
      }

      // 2. Moving Obstacle: Red Triangle (Walking Patron)
      const cx = obs.x + obs.w / 2;
      const cy = obs.y + obs.h / 2;
      const angle = obs.heading;

      ctx.save();
      ctx.translate(cx, cy);
      ctx.rotate(angle);

      // Red Triangle oriented forward
      const size = Math.max(obs.w, obs.h) * 0.65;
      ctx.fillStyle = '#dc2626';
      ctx.strokeStyle = '#991b1b';
      ctx.lineWidth = 2;
      ctx.shadowColor = '#dc2626';
      ctx.shadowBlur = 6;

      ctx.beginPath();
      ctx.moveTo(size, 0);                 // Front tip
      ctx.lineTo(-size * 0.8, -size * 0.7); // Back left
      ctx.lineTo(-size * 0.5, 0);           // Inward rear indent
      ctx.lineTo(-size * 0.8, size * 0.7);  // Back right
      ctx.closePath();
      ctx.fill();
      ctx.stroke();

      // White center indicator dot
      ctx.fillStyle = '#ffffff';
      ctx.beginPath();
      ctx.arc(0, 0, 3, 0, Math.PI * 2);
      ctx.fill();

      ctx.restore();
    });
  }

  drawUsers(ctx, isDark) {
    this.users.forEach(user => {
      const radius = 8;
      ctx.save();

      // Halo/glow if threatened or dropped
      if (user.isDropped) {
        ctx.fillStyle = '#ef4444';
        ctx.strokeStyle = '#991b1b';
      } else if (user.threatTimer > 0) {
        ctx.fillStyle = '#f97316';
        ctx.strokeStyle = '#c2410c';
        ctx.shadowColor = '#f97316';
        ctx.shadowBlur = 8;
      } else {
        ctx.fillStyle = '#16a34a';
        ctx.strokeStyle = '#15803d';
      }

      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.arc(user.x, user.y, radius, 0, Math.PI * 2);
      ctx.fill();
      ctx.stroke();

      // User Label
      ctx.font = 'bold 8px "Inter", sans-serif';
      ctx.fillStyle = '#ffffff';
      ctx.textAlign = 'center';
      ctx.fillText(`U${user.id}`, user.x, user.y + 3);

      ctx.restore();
    });
  }

  drawAccessPoints(ctx, isDark) {
    this.aps.forEach(ap => {
      const isFull = ap.isFull;
      const isNearFull = ap.load === ap.maxCapacity - 1;

      // 1. Radio / Optical beacon pulse glow
      const pulseRadius = ap.radius + 8 + Math.sin(ap.pulsePhase) * 4;
      ap.pulsePhase += 0.04;

      ctx.save();
      const glowColor = isFull
        ? 'rgba(239, 68, 68, 0.25)'
        : (isNearFull ? 'rgba(245, 158, 11, 0.25)' : 'rgba(37, 99, 235, 0.25)');

      ctx.fillStyle = glowColor;
      ctx.beginPath();
      ctx.arc(ap.x, ap.y, pulseRadius, 0, Math.PI * 2);
      ctx.fill();

      // 2. Distinct Royal Blue Circle (Access Point ceiling node)
      ctx.fillStyle = isFull ? '#dc2626' : (isNearFull ? '#d97706' : '#2563eb');
      ctx.strokeStyle = isDark ? '#93c5fd' : '#1d4ed8';
      ctx.lineWidth = 2.5;
      ctx.shadowColor = '#2563eb';
      ctx.shadowBlur = isDark ? 10 : 4;

      ctx.beginPath();
      ctx.arc(ap.x, ap.y, ap.radius, 0, Math.PI * 2);
      ctx.fill();
      ctx.stroke();

      // 3. Inner White Optical Diode
      ctx.fillStyle = '#ffffff';
      ctx.beginPath();
      ctx.arc(ap.x, ap.y, 4, 0, Math.PI * 2);
      ctx.fill();

      // 4. Capacity Badge Label (e.g. "AP-1: 2/3")
      const badgeText = `AP-${ap.id + 1} [${ap.load}/${ap.maxCapacity}]`;
      ctx.font = 'bold 10px "JetBrains Mono", monospace';
      const textWidth = ctx.measureText(badgeText).width;
      const badgeW = textWidth + 12;
      const badgeH = 18;
      const badgeX = ap.x - badgeW / 2;
      const badgeY = ap.y - ap.radius - 22;

      ctx.fillStyle = isFull ? '#ef4444' : (isNearFull ? '#f59e0b' : '#1e40af');
      ctx.beginPath();
      ctx.roundRect(badgeX, badgeY, badgeW, badgeH, 4);
      ctx.fill();

      ctx.fillStyle = '#ffffff';
      ctx.textAlign = 'center';
      ctx.fillText(badgeText, ap.x, badgeY + 12);

      ctx.restore();
    });
  }

  // ==========================================================================
  // MAIN ANIMATION & UPDATE LOOP
  // ==========================================================================

  loop(timestamp) {
    const dt = (timestamp - this.lastFrameTime) / 1000;
    this.lastFrameTime = timestamp;

    this.frameCount++;
    if (this.frameCount % 30 === 0) {
      this.fps = Math.round(1 / dt) || 60;
      const fpsEl = document.getElementById('canvas-fps-badge');
      if (fpsEl) fpsEl.textContent = `${this.fps} FPS`;
    }

    if (!this.isPaused) {
      this.stats.simTimeSeconds += dt;
      this.updatePhysics(this.speedMultiplier);
      this.updateBeamScheduling();
    }

    this.render();
    this.updateHUD();

    requestAnimationFrame((t) => this.loop(t));
  }

  updatePhysics(speedFactor) {
    this.obstacles.forEach(obs => obs.update(speedFactor, this.nativeWidth, this.nativeHeight));
  }

  updateHUD() {
    // Timer display
    const mins = Math.floor(this.stats.simTimeSeconds / 60);
    const secs = (this.stats.simTimeSeconds % 60).toFixed(1);
    const timeEl = document.getElementById('canvas-sim-time');
    if (timeEl) {
      timeEl.textContent = `${mins.toString().padStart(2, '0')}:${secs.padStart(4, '0')}`;
    }
  }

  updateUI() {
    // Update KPI numbers
    const elConnected = document.getElementById('stat-connected-users');
    const elProactive = document.getElementById('stat-proactive-handovers');
    const elRedirects = document.getElementById('stat-load-redirects');
    const elDrops = document.getElementById('stat-physical-drops');

    const connectedCount = this.users.filter(u => u.currentAp !== null).length;
    if (elConnected) elConnected.textContent = connectedCount;
    if (elProactive) elProactive.textContent = this.stats.proactiveHandovers;
    if (elRedirects) elRedirects.textContent = this.stats.loadRedirects;
    if (elDrops) elDrops.textContent = this.stats.physicalDrops;

    // Update AP Meters Matrix
    const metersContainer = document.getElementById('ap-meters-container');
    if (metersContainer) {
      let html = '';
      let totalCapacity = 0;
      let totalAssigned = 0;

      this.aps.forEach(ap => {
        totalCapacity += ap.maxCapacity;
        totalAssigned += ap.load;
        const pct = Math.min(100, Math.round((ap.load / ap.maxCapacity) * 100));

        let barColor = 'bg-blue-600';
        if (ap.load >= ap.maxCapacity) barColor = 'bg-red-500 animate-pulse';
        else if (ap.load === ap.maxCapacity - 1) barColor = 'bg-amber-500';

        html += `
          <div>
            <div class="flex items-center justify-between text-[11px] mb-1">
              <span class="font-bold text-slate-700 dark:text-slate-200">AP-${ap.id + 1}</span>
              <span class="font-mono text-slate-500">${ap.load}/${ap.maxCapacity} (${pct}%)</span>
            </div>
            <div class="w-full bg-slate-200 dark:bg-slate-700/60 rounded-full h-2 overflow-hidden">
              <div class="${barColor} h-2 rounded-full transition-all duration-300" style="width: ${pct}%"></div>
            </div>
          </div>
        `;
      });

      metersContainer.innerHTML = html;

      const satEl = document.getElementById('stat-network-saturation');
      if (satEl && totalCapacity > 0) {
        const satPct = Math.round((totalAssigned / totalCapacity) * 100);
        satEl.textContent = `${satPct}% Saturated`;
      }
    }
  }

  logEvent(msg, type = 'system-info') {
    const list = document.getElementById('eventLogList');
    if (!list) return;

    const timeStr = new Date().toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' });
    const entry = document.createElement('div');
    entry.className = `log-entry ${type} p-1.5 rounded text-[11px] font-mono leading-tight`;
    entry.innerHTML = `<span class="text-slate-400">[${timeStr}]</span> ${msg}`;

    list.insertBefore(entry, list.firstChild);

    // Limit log memory to 40 items
    while (list.children.length > 40) {
      list.removeChild(list.lastChild);
    }
  }

  // ==========================================================================
  // EVENT BINDINGS & VIEW SWITCHING
  // ==========================================================================

  setSolution(solution) {
    this.activeSolution = solution;

    const viewHome = document.getElementById('view-home');
    const viewSim = document.getElementById('view-simulation');
    const navHome = document.getElementById('nav-btn-home');
    const navLB = document.getElementById('nav-btn-load-balance');
    const navPred = document.getElementById('nav-btn-predictive');

    if (solution === 'home') {
      viewHome.classList.remove('hidden');
      viewSim.classList.add('hidden');
      navHome.classList.add('active');
      navLB.classList.remove('active');
      navPred.classList.remove('active');
      return;
    }

    viewHome.classList.add('hidden');
    viewSim.classList.remove('hidden');
    navHome.classList.remove('active');

    const titleEl = document.getElementById('solution-title');
    const subEl = document.getElementById('solution-subtitle');
    const tagEl = document.getElementById('solution-mode-tag');
    const switchBtnText = document.getElementById('btn-switch-solution-text');
    const presetsContainer = document.getElementById('solution-presets-container');

    if (solution === 'load-balance') {
      navLB.classList.add('active');
      navPred.classList.remove('active');
      titleEl.textContent = 'Page 1: Load Balancing & Overload Redirection';
      subEl.textContent = 'Observing dynamic user re-allocation when APs reach maximum capacity threshold (3 users/AP).';
      tagEl.textContent = 'Mode: Capacity Limit';
      tagEl.className = 'text-[10px] font-mono px-2 py-0.5 rounded bg-blue-500/10 text-blue-400 border border-blue-500/20 uppercase font-semibold';
      switchBtnText.textContent = 'Switch to Predictive Sensing';

      // Load Balancing Action Buttons
      presetsContainer.innerHTML = `
        <button id="btn-action-overload" class="px-2.5 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-700 text-white text-xs font-medium transition">
          Burst Overload AP-2
        </button>
        <button id="btn-action-rebalance" class="px-2.5 py-1.5 rounded-lg border border-slate-300 dark:border-slate-700 hover:bg-slate-100 dark:hover:bg-slate-800 text-xs font-medium transition">
          Rebalance All
        </button>
      `;

      document.getElementById('btn-action-overload')?.addEventListener('click', () => this.triggerAP2Overload());
      document.getElementById('btn-action-rebalance')?.addEventListener('click', () => this.triggerRebalanceAll());
    } else {
      navLB.classList.remove('active');
      navPred.classList.add('active');
      titleEl.textContent = 'Page 2: Proactive Obstacle Sensing & Predictive Handover';
      subEl.textContent = 'Demonstrating zero-latency Orange -> Green handovers before walking obstacles ever cut the beam.';
      tagEl.textContent = 'Mode: Predictive Warning';
      tagEl.className = 'text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 uppercase font-semibold';
      switchBtnText.textContent = 'Switch to Load Balancing';

      // Predictive Sensing Action Buttons
      presetsContainer.innerHTML = `
        <button id="btn-action-fast-patron" class="px-2.5 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-medium transition">
          Fast Patron
        </button>
        <button id="btn-action-slow-mo" class="px-2.5 py-1.5 rounded-lg border border-slate-300 dark:border-slate-700 hover:bg-slate-100 dark:hover:bg-slate-800 text-xs font-medium transition">
          Slow-Mo (0.25x)
        </button>
        <button id="btn-action-compare-mode" class="px-2.5 py-1.5 rounded-lg border border-amber-500/40 hover:bg-amber-500/10 text-amber-500 text-xs font-medium transition">
          ${this.reactiveModeOnly ? 'Reactive' : 'Proactive'} Mode
        </button>
      `;

      document.getElementById('btn-action-fast-patron')?.addEventListener('click', () => this.triggerFastCrossing());
      document.getElementById('btn-action-slow-mo')?.addEventListener('click', () => this.triggerSlowMotion());
      document.getElementById('btn-action-compare-mode')?.addEventListener('click', (e) => {
        this.toggleProactiveVsReactive();
        e.target.textContent = this.reactiveModeOnly ? 'Reactive Mode' : 'Proactive Mode';
      });
    }

    lucide.createIcons();
    this.updateUI();
  }

  bindEvents() {
    // Navigation
    document.getElementById('nav-brand-btn')?.addEventListener('click', () => this.setSolution('home'));
    document.getElementById('nav-btn-home')?.addEventListener('click', () => this.setSolution('home'));
    document.getElementById('nav-btn-load-balance')?.addEventListener('click', () => this.setSolution('load-balance'));
    document.getElementById('nav-btn-predictive')?.addEventListener('click', () => this.setSolution('predictive'));

    document.getElementById('home-launch-solution-1')?.addEventListener('click', () => this.setSolution('load-balance'));
    document.getElementById('card-launch-solution-1')?.addEventListener('click', () => this.setSolution('load-balance'));
    document.getElementById('home-launch-solution-2')?.addEventListener('click', () => this.setSolution('predictive'));
    document.getElementById('card-launch-solution-2')?.addEventListener('click', () => this.setSolution('predictive'));

    document.getElementById('btn-switch-solution')?.addEventListener('click', () => {
      this.setSolution(this.activeSolution === 'load-balance' ? 'predictive' : 'load-balance');
    });

    // Play / Pause
    const playPauseBtn = document.getElementById('btn-play-pause');
    const stepBtn = document.getElementById('btn-step-frame');
    playPauseBtn?.addEventListener('click', () => {
      this.isPaused = !this.isPaused;
      const icon = document.getElementById('icon-play-pause');
      const text = document.getElementById('text-play-pause');
      if (this.isPaused) {
        text.textContent = 'Play [Space]';
        icon.setAttribute('data-lucide', 'play');
        stepBtn.removeAttribute('disabled');
      } else {
        text.textContent = 'Pause [Space]';
        icon.setAttribute('data-lucide', 'pause');
        stepBtn.setAttribute('disabled', 'true');
      }
      lucide.createIcons();
      this.logEvent(`Simulation ${this.isPaused ? 'PAUSED' : 'RESUMED'}`, 'system-info');
    });

    // Step Forward
    stepBtn?.addEventListener('click', () => this.stepForward());

    // Reset
    document.getElementById('btn-reset-sim')?.addEventListener('click', () => this.resetSimulation());

    // Speed Slider
    const speedSlider = document.getElementById('slider-speed');
    const speedLabel = document.getElementById('label-speed');
    speedSlider?.addEventListener('input', (e) => {
      this.speedMultiplier = parseFloat(e.target.value);
      speedLabel.textContent = `${this.speedMultiplier.toFixed(1)}x`;
    });

    // Capacity Selector
    document.getElementById('select-capacity')?.addEventListener('change', (e) => {
      this.setCapacityLimit(e.target.value);
    });

    // Beam Style
    document.getElementById('select-beam-style')?.addEventListener('change', (e) => {
      this.beamStyle = e.target.value;
      this.logEvent(`Beam rendering style set to: ${this.beamStyle.toUpperCase()}`, 'system-info');
    });

    // Toggle Grid
    const gridBtn = document.getElementById('btn-toggle-grid');
    gridBtn?.addEventListener('click', () => {
      this.showGrid = !this.showGrid;
      gridBtn.textContent = `Grid: ${this.showGrid ? 'ON' : 'OFF'}`;
    });

    // Toggle Zones
    const zonesBtn = document.getElementById('btn-toggle-zones');
    zonesBtn?.addEventListener('click', () => {
      this.showZones = !this.showZones;
      zonesBtn.textContent = `Zones: ${this.showZones ? 'ON' : 'OFF'}`;
      zonesBtn.className = `px-2 py-1 rounded bg-slate-900/80 backdrop-blur border border-slate-700 text-[10px] ${this.showZones ? 'text-amber-400' : 'text-slate-400'} font-mono transition`;
    });

    // Clear Log
    document.getElementById('btn-clear-log')?.addEventListener('click', () => {
      const list = document.getElementById('eventLogList');
      if (list) list.innerHTML = '';
    });

    // Theme Toggle
    const themeBtn = document.getElementById('btn-theme-toggle');
    themeBtn?.addEventListener('click', () => {
      const html = document.documentElement;
      const isDark = html.classList.toggle('dark');
      const sun = document.getElementById('icon-sun');
      const moon = document.getElementById('icon-moon');
      if (isDark) {
        sun.classList.add('hidden');
        moon.classList.remove('hidden');
      } else {
        sun.classList.remove('hidden');
        moon.classList.add('hidden');
      }
      lucide.createIcons();
    });

    // Audio Toggle
    const audioBtn = document.getElementById('btn-audio-toggle');
    audioBtn?.addEventListener('click', () => {
      this.audio.enabled = !this.audio.enabled;
      const icon = document.getElementById('icon-audio');
      if (this.audio.enabled) {
        icon.setAttribute('data-lucide', 'volume-2');
        audioBtn.classList.remove('opacity-50');
      } else {
        icon.setAttribute('data-lucide', 'volume-x');
        audioBtn.classList.add('opacity-50');
      }
      lucide.createIcons();
    });

    // Modal
    const infoBtn = document.getElementById('btn-info-modal');
    const modal = document.getElementById('infoModal');
    const closeBtn = document.getElementById('btn-close-modal');
    const gotItBtn = document.getElementById('btn-modal-gotit');

    infoBtn?.addEventListener('click', () => modal.classList.remove('hidden'));
    closeBtn?.addEventListener('click', () => modal.classList.add('hidden'));
    gotItBtn?.addEventListener('click', () => modal.classList.add('hidden'));
    modal?.addEventListener('click', (e) => {
      if (e.target === modal) modal.classList.add('hidden');
    });

    // Keyboard Shortcuts
    window.addEventListener('keydown', (e) => {
      if (e.target.tagName === 'INPUT' || e.target.tagName === 'SELECT') return;
      if (e.code === 'Space') {
        e.preventDefault();
        playPauseBtn?.click();
      } else if (e.key === '.') {
        this.stepForward();
      } else if (e.key.toLowerCase() === 'r') {
        this.resetSimulation();
      } else if (e.key === '1') {
        this.setSolution('load-balance');
      } else if (e.key === '2') {
        this.setSolution('predictive');
      } else if (e.key.toLowerCase() === 'h') {
        this.setSolution('home');
      }
    });

    // Canvas Hover Inspection
    this.canvas.addEventListener('mousemove', (e) => {
      const rect = this.canvas.getBoundingClientRect();
      const scaleX = this.nativeWidth / rect.width;
      const scaleY = this.nativeHeight / rect.height;
      this.mousePos = {
        x: (e.clientX - rect.left) * scaleX,
        y: (e.clientY - rect.top) * scaleY
      };

      this.inspectCanvasEntity(e.clientX, e.clientY);
    });

    this.canvas.addEventListener('mouseleave', () => {
      const tooltip = document.getElementById('canvasTooltip');
      if (tooltip) tooltip.classList.add('hidden');
    });

    // Window Resize Handling for Retina Canvas
    window.addEventListener('resize', () => this.setupCanvasDPI());
  }

  inspectCanvasEntity(clientX, clientY) {
    const tooltip = document.getElementById('canvasTooltip');
    const titleEl = document.getElementById('tooltip-title');
    const bodyEl = document.getElementById('tooltip-body');
    if (!tooltip) return;

    const m = this.mousePos;
    let found = null;

    // Check APs
    for (const ap of this.aps) {
      if (MathUtils.distance(m, ap.pos) <= ap.radius + 6) {
        found = {
          type: 'ap',
          title: `Access Point AP-${ap.id + 1}`,
          data: [
            `Load: ${ap.load} / ${ap.maxCapacity} connected`,
            `Status: ${ap.isFull ? 'SATURATED' : 'AVAILABLE'}`,
            `Optical Band: 430 THz Visible Light`,
            `Output Power: 18.5 dBm`
          ]
        };
        break;
      }
    }

    // Check Users
    if (!found) {
      for (const u of this.users) {
        if (MathUtils.distance(m, u.pos) <= 12) {
          const apText = u.currentAp ? `AP-${u.currentAp.id + 1}` : 'Disconnected';
          const statusText = u.isDropped ? 'Dropped (Physical Cut)' : (u.threatTimer > 0 ? 'Threat Warning (Orange)' : 'Active High-Speed');
          found = {
            type: 'user',
            title: `Stationary User #U${u.id}`,
            data: [
              `Assigned: ${apText}`,
              `Link Status: ${statusText}`,
              `SNR: ${u.currentAp ? (32.4 - u.currentAp.distanceTo(u.pos) * 0.02).toFixed(1) : 0} dB`,
              `Zone: Table ${u.tableId}`
            ]
          };
          break;
        }
      }
    }

    // Check Obstacles
    if (!found) {
      for (const obs of this.obstacles) {
        if (MathUtils.pointInRect(m, obs.rect)) {
          found = {
            type: 'obstacle',
            title: `Moving Patron #${obs.id}`,
            data: [
              `Lane: ${obs.laneType.toUpperCase()} walkway`,
              `Velocity: (${obs.vx.toFixed(1)}, ${obs.vy.toFixed(1)})`,
              `Warning Distance: ${obs.leadDistance} px`,
              `Trajectory: Oriented Forward`
            ]
          };
          break;
        }
      }
    }

    if (found) {
      titleEl.textContent = found.title;
      bodyEl.innerHTML = found.data.map(d => `<div>${d}</div>`).join('');
      tooltip.classList.remove('hidden');

      // Position tooltip near cursor with viewport bounds clamp
      const wrapperRect = this.canvas.parentElement.getBoundingClientRect();
      const tipX = Math.min(wrapperRect.width - 170, Math.max(10, clientX - wrapperRect.left + 15));
      const tipY = Math.min(wrapperRect.height - 110, Math.max(10, clientY - wrapperRect.top + 15));

      tooltip.style.left = `${tipX}px`;
      tooltip.style.top = `${tipY}px`;
    } else {
      tooltip.classList.add('hidden');
    }
  }
}

// ============================================================================
// BOOTSTRAP INITIALIZATION
// ============================================================================

window.addEventListener('DOMContentLoaded', () => {
  window.lifiApp = new LiFiDigitalTwin();
  console.log('[LuminaLanes] Li-Fi Digital Twin engine running at 60 FPS.');
});
