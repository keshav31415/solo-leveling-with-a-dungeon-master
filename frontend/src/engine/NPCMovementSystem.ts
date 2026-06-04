import type { NPCMovementConfig } from './types';
import type { EntityManager } from './EntityManager';
import type { Pathfinder } from './Pathfinder';

const DEFAULT_STEP_COOLDOWN = 10;

interface InternalConfig extends NPCMovementConfig {
  homePosition: { x: number; y: number }
  _destination: { x: number; y: number } | null
  _stepTimer: number    // frames to wait between animation steps
  _pauseTimer: number   // frames to stand still at destination
  _waypointIndex: number
  _orbitAngle: number
}

export class NPCMovementSystem {
  private configs: Map<string, InternalConfig> = new Map();

  constructor(
    private entityManager: EntityManager,
    private pathfinder: Pathfinder,
  ) {}

  setMovement(entityId: string, config: NPCMovementConfig) {
    const entity = this.entityManager.getEntity(entityId);
    const home = config.homePosition
      ?? (entity ? { x: entity.gridX, y: entity.gridY } : { x: 0, y: 0 });

    this.configs.set(entityId, {
      ...config,
      homePosition: home,
      _destination: null,
      _stepTimer: 0,
      _pauseTimer: Math.floor(Math.random() * 40), // stagger initial starts
      _waypointIndex: 0,
      _orbitAngle: Math.random() * Math.PI * 2,
    });
  }

  clearMovement(entityId: string) {
    this.configs.delete(entityId);
  }

  getMovement(entityId: string): NPCMovementConfig | undefined {
    return this.configs.get(entityId);
  }

  update() {
    for (const [entityId, config] of this.configs.entries()) {
      const entity = this.entityManager.getEntity(entityId);
      if (!entity || entity.isPlayer) continue;
      if (entity.isMoving) continue;
      if (entity.state === 'dead' || entity.state === 'dead_ash') continue;
      if (config.behavior === 'idle') continue;

      // Wait between steps
      if (config._stepTimer > 0) { config._stepTimer--; continue; }

      // Wait at destination
      if (config._pauseTimer > 0) { config._pauseTimer--; continue; }

      // Arrived at destination (or no destination yet)
      if (
        config._destination === null ||
        (entity.gridX === config._destination.x && entity.gridY === config._destination.y)
      ) {
        if (config._destination !== null) {
          // Just arrived — apply arrival pause, clear destination
          config._pauseTimer = this.pauseFor(config);
          config._destination = null;
        } else {
          // Need a new destination
          const dest = this.pickDestination(entityId, config);
          if (dest) config._destination = dest;
          else config._pauseTimer = 20; // nothing found, wait briefly
        }
        continue;
      }

      // Step one tile toward destination
      const path = this.pathfinder.findPath(
        entity.gridX, entity.gridY,
        config._destination.x, config._destination.y,
      );

      if (path.length === 0) {
        config._destination = null; // unreachable — repick next cycle
        continue;
      }

      const next = path[0];
      const moved = this.entityManager.tryMove(
        entityId,
        next.x - entity.gridX,
        next.y - entity.gridY,
      );
      if (moved) config._stepTimer = config.stepCooldown ?? DEFAULT_STEP_COOLDOWN;
    }
  }

  // ── How long to pause when arriving at a destination ─────────────────────────

  private pauseFor(config: InternalConfig): number {
    switch (config.behavior) {
      case 'wander':  return 40 + Math.floor(Math.random() * 80);  // 0.7 – 2 s
      case 'flee':    return 0;
      case 'seek':    return 0;
      case 'patrol':  return 20 + Math.floor(Math.random() * 40);
      case 'battle':  return 5  + Math.floor(Math.random() * 15);
      default:        return 0;
    }
  }

  // ── Route each behavior to its destination picker ────────────────────────────

  private pickDestination(
    entityId: string,
    config: InternalConfig,
  ): { x: number; y: number } | null {
    switch (config.behavior) {
      case 'wander':  return this.wanderDest(entityId, config);
      case 'flee':    return this.fleeDest(entityId, config);
      case 'seek':    return this.seekDest(config);
      case 'patrol':  return this.patrolDest(entityId, config);
      case 'battle':  return this.battleDest(entityId, config);
      default:        return null;
    }
  }

  // ── Wander: random point within radius, far enough to feel like real movement ─

  private wanderDest(entityId: string, config: InternalConfig): { x: number; y: number } | null {
    const entity = this.entityManager.getEntity(entityId)!;
    const { homePosition: home, wanderRadius = 6 } = config;
    const minDist = Math.max(3, wanderRadius * 0.5);

    for (let attempt = 0; attempt < 10; attempt++) {
      const angle = Math.random() * Math.PI * 2;
      const dist = minDist + Math.random() * (wanderRadius - minDist);
      const tx = Math.round(home.x + Math.cos(angle) * dist);
      const ty = Math.round(home.y + Math.sin(angle) * dist);

      // Skip if too close to current position (avoid micro-moves)
      if (Math.abs(tx - entity.gridX) + Math.abs(ty - entity.gridY) < 2) continue;

      if (this.pathfinder.findPath(entity.gridX, entity.gridY, tx, ty).length > 0) {
        return { x: tx, y: ty };
      }
    }
    return null;
  }

  // ── Flee: farthest reachable tile in flee direction ───────────────────────────

  private fleeDest(entityId: string, config: InternalConfig): { x: number; y: number } | null {
    const entity = this.entityManager.getEntity(entityId)!;
    const threat = this.resolvePosition(config.fleeFrom);
    if (!threat) return null;

    const fx = entity.gridX - threat.x;
    const fy = entity.gridY - threat.y;
    const norm = Math.sqrt(fx * fx + fy * fy) || 1;
    const ux = fx / norm;
    const uy = fy / norm;

    // Try far-to-near until a reachable tile is found
    for (let dist = 14; dist >= 3; dist -= 2) {
      const tx = Math.round(entity.gridX + ux * dist);
      const ty = Math.round(entity.gridY + uy * dist);
      if (this.pathfinder.findPath(entity.gridX, entity.gridY, tx, ty).length > 0) {
        return { x: tx, y: ty };
      }
    }
    return null;
  }

  // ── Seek: walk toward a target entity or coordinate ──────────────────────────

  private seekDest(config: InternalConfig): { x: number; y: number } | null {
    return this.resolvePosition(config.target);
  }

  // ── Patrol: cycle through waypoints ──────────────────────────────────────────

  private patrolDest(entityId: string, config: InternalConfig): { x: number; y: number } | null {
    const entity = this.entityManager.getEntity(entityId)!;
    const { waypoints = [] } = config;
    if (waypoints.length === 0) return null;

    const wp = waypoints[config._waypointIndex];
    if (entity.gridX === wp.x && entity.gridY === wp.y) {
      config._waypointIndex = (config._waypointIndex + 1) % waypoints.length;
    }
    return waypoints[config._waypointIndex];
  }

  // ── Battle: orbit around target at a fixed radius ────────────────────────────

  private battleDest(entityId: string, config: InternalConfig): { x: number; y: number } | null {
    const entity = this.entityManager.getEntity(entityId)!;
    const target = this.resolvePosition(config.target);
    if (!target) return null;

    const orbitRadius = config.orbitRadius ?? 4;
    // Advance orbit angle by a random arc (0.4–1.2 rad), random direction
    config._orbitAngle += (0.4 + Math.random() * 0.8) * (Math.random() < 0.5 ? 1 : -1);

    // Try the updated angle, then sweep until a walkable orbit point is found
    for (let offset = 0; offset < Math.PI * 2; offset += 0.4) {
      const angle = config._orbitAngle + offset;
      const tx = Math.round(target.x + Math.cos(angle) * orbitRadius);
      const ty = Math.round(target.y + Math.sin(angle) * orbitRadius);
      if (this.pathfinder.findPath(entity.gridX, entity.gridY, tx, ty).length > 0) {
        return { x: tx, y: ty };
      }
    }
    return null;
  }

  // ── Resolve entity ID or raw coordinate ──────────────────────────────────────

  private resolvePosition(
    ref: string | { x: number; y: number } | undefined,
  ): { x: number; y: number } | null {
    if (!ref) return null;
    if (typeof ref === 'string') {
      const e = this.entityManager.getEntity(ref);
      return e ? { x: e.gridX, y: e.gridY } : null;
    }
    return ref;
  }
}
