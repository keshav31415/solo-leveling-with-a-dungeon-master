// ============================================================
// Entity Manager — Manages all entities and renders Layer 2
// ============================================================

import { TILE_SIZE } from './types';
import type { EntityData } from './types';
import type { TileMap } from './TileMap';

export class EntityManager {
  private entities: Map<string, EntityData> = new Map();
  private tileMap: TileMap;

  constructor(initialEntities: EntityData[], tileMap: TileMap) {
    this.tileMap = tileMap;
    for (const entity of initialEntities) {
      // Initialize pixel positions from grid positions
      entity.pixelX = entity.gridX * TILE_SIZE;
      entity.pixelY = entity.gridY * TILE_SIZE;
      entity.targetGridX = entity.gridX;
      entity.targetGridY = entity.gridY;
      this.entities.set(entity.id, entity);
    }
  }

  /** Get an entity by ID */
  getEntity(id: string): EntityData | undefined {
    return this.entities.get(id);
  }

  /** Get the player entity */
  getPlayer(): EntityData | undefined {
    for (const entity of this.entities.values()) {
      if (entity.isPlayer) return entity;
    }
    return undefined;
  }

  /** Get all entities */
  getAllEntities(): EntityData[] {
    return Array.from(this.entities.values());
  }

  /** Try to move an entity by one tile in a direction */
  tryMove(entityId: string, dx: number, dy: number): boolean {
    const entity = this.entities.get(entityId);
    if (!entity || entity.isMoving) return false;
    if (entity.state === 'dead' || entity.state === 'dead_ash') return false;

    const newGridX = entity.gridX + dx;
    const newGridY = entity.gridY + dy;

    // Set direction regardless of whether move succeeds
    if (dx === -1) entity.direction = 'left';
    if (dx === 1) entity.direction = 'right';
    if (dy === -1) entity.direction = 'up';
    if (dy === 1) entity.direction = 'down';

    // Check map collision
    if (!this.tileMap.isWalkable(newGridX, newGridY)) return false;

    // Check entity collision (for entities wider than 1 tile)
    for (const other of this.entities.values()) {
      if (other.id === entityId) continue;
      if (other.state === 'dead' || other.state === 'dead_ash') continue;

      // Simple AABB overlap check
      if (
        newGridX < other.gridX + other.width &&
        newGridX + entity.width > other.gridX &&
        newGridY < other.gridY + other.height &&
        newGridY + entity.height > other.gridY
      ) {
        return false; // blocked by another entity
      }
    }

    // Start smooth movement
    entity.targetGridX = newGridX;
    entity.targetGridY = newGridY;
    entity.gridX = newGridX;
    entity.gridY = newGridY;
    entity.isMoving = true;
    entity.state = 'walking';

    return true;
  }

  /** Update all entities (smooth pixel interpolation) */
  update() {
    for (const entity of this.entities.values()) {
      const targetPixelX = entity.gridX * TILE_SIZE;
      const targetPixelY = entity.gridY * TILE_SIZE;

      if (entity.isMoving) {
        // Move pixel position towards target
        const diffX = targetPixelX - entity.pixelX;
        const diffY = targetPixelY - entity.pixelY;

        if (Math.abs(diffX) <= entity.speed && Math.abs(diffY) <= entity.speed) {
          // Arrived
          entity.pixelX = targetPixelX;
          entity.pixelY = targetPixelY;
          entity.isMoving = false;
          entity.state = 'idle';
        } else {
          // Keep moving
          if (diffX !== 0) entity.pixelX += Math.sign(diffX) * entity.speed;
          if (diffY !== 0) entity.pixelY += Math.sign(diffY) * entity.speed;
        }
      }
    }
  }

  /** Check if the player is adjacent to an interactable entity */
  getInteractableNearPlayer(): EntityData | null {
    const player = this.getPlayer();
    if (!player) return null;

    // Check the tile the player is facing
    let checkX = player.gridX;
    let checkY = player.gridY;

    switch (player.direction) {
      case 'up': checkY -= 1; break;
      case 'down': checkY += 1; break;
      case 'left': checkX -= 1; break;
      case 'right': checkX += 1; break;
    }

    for (const entity of this.entities.values()) {
      if (!entity.isInteractable) continue;
      if (entity.state === 'dead' || entity.state === 'dead_ash') continue;

      // Check if the facing tile overlaps with this entity
      if (
        checkX >= entity.gridX &&
        checkX < entity.gridX + entity.width &&
        checkY >= entity.gridY &&
        checkY < entity.gridY + entity.height
      ) {
        return entity;
      }
    }

    return null;
  }

  /** Set an entity's state (used by GameAPI for AI) */
  setEntityState(entityId: string, state: string) {
    const entity = this.entities.get(entityId);
    if (entity) {
      entity.state = state;

      // If the entrance door closes, make it solid in the collision map
      if (entityId === 'entrance_door' && state === 'closed') {
        for (let x = entity.gridX; x < entity.gridX + entity.width; x++) {
          this.tileMap.setCollision(x, entity.gridY, 1);
        }
      }
    }
  }

  /** Render all entities to Layer 2 canvas */
  render(ctx: CanvasRenderingContext2D, cameraX: number, cameraY: number) {
    // Sort entities by Y position so lower ones draw on top (depth sorting)
    const sorted = this.getAllEntities().sort((a, b) => a.pixelY - b.pixelY);

    for (const entity of sorted) {
      if (entity.state === 'dead_ash') {
        this.renderDeadEntity(ctx, entity, cameraX, cameraY);
        continue;
      }
      if (entity.state === 'dead') continue; // fully dead, invisible

      // Special rendering for the entrance door
      if (entity.id === 'entrance_door') {
        this.renderDoor(ctx, entity, cameraX, cameraY);
        continue;
      }

      const screenX = entity.pixelX - cameraX;
      const screenY = entity.pixelY - cameraY;
      const w = TILE_SIZE * entity.width;
      const h = TILE_SIZE * entity.height;

      // Draw placeholder body
      ctx.fillStyle = entity.color;
      ctx.fillRect(screenX + 4, screenY + 4, w - 8, h - 8);

      // Draw outline
      ctx.strokeStyle = entity.outlineColor;
      ctx.lineWidth = 2;
      ctx.strokeRect(screenX + 4, screenY + 4, w - 8, h - 8);

      // Draw direction indicator (a small triangle showing which way they face)
      ctx.fillStyle = '#ffffff';
      const centerX = screenX + w / 2;
      const centerY = screenY + h / 2;
      ctx.beginPath();
      switch (entity.direction) {
        case 'up':
          ctx.moveTo(centerX, screenY + 6);
          ctx.lineTo(centerX - 4, screenY + 12);
          ctx.lineTo(centerX + 4, screenY + 12);
          break;
        case 'down':
          ctx.moveTo(centerX, screenY + h - 6);
          ctx.lineTo(centerX - 4, screenY + h - 12);
          ctx.lineTo(centerX + 4, screenY + h - 12);
          break;
        case 'left':
          ctx.moveTo(screenX + 6, centerY);
          ctx.lineTo(screenX + 12, centerY - 4);
          ctx.lineTo(screenX + 12, centerY + 4);
          break;
        case 'right':
          ctx.moveTo(screenX + w - 6, centerY);
          ctx.lineTo(screenX + w - 12, centerY - 4);
          ctx.lineTo(screenX + w - 12, centerY + 4);
          break;
      }
      ctx.closePath();
      ctx.fill();

      // Draw label below entity
      ctx.fillStyle = 'rgba(255, 255, 255, 0.8)';
      ctx.font = '10px monospace';
      ctx.textAlign = 'center';
      ctx.fillText(entity.label, centerX, screenY + h + 10);
    }
  }

  private renderDeadEntity(
    ctx: CanvasRenderingContext2D,
    entity: EntityData,
    cameraX: number,
    cameraY: number
  ) {
    const screenX = entity.pixelX - cameraX;
    const screenY = entity.pixelY - cameraY;
    const w = TILE_SIZE * entity.width;
    const h = TILE_SIZE * entity.height;

    // Draw as a small gray pile of ash
    ctx.fillStyle = 'rgba(80, 80, 80, 0.6)';
    ctx.beginPath();
    ctx.ellipse(
      screenX + w / 2,
      screenY + h - 6,
      w / 3,
      6,
      0,
      0,
      Math.PI * 2
    );
    ctx.fill();
  }

  private renderDoor(
    ctx: CanvasRenderingContext2D,
    entity: EntityData,
    cameraX: number,
    cameraY: number
  ) {
    const screenX = entity.pixelX - cameraX;
    const screenY = entity.pixelY - cameraY;
    const w = TILE_SIZE * entity.width;
    const h = TILE_SIZE * entity.height;

    if (entity.state === 'open') {
      // Open gate — brown frame with a dark gap in the center
      ctx.fillStyle = '#3d2b1a';
      ctx.fillRect(screenX, screenY, w, h);

      // Dark opening in the center (walkable gap)
      ctx.fillStyle = '#0a0a14';
      ctx.fillRect(screenX + 8, screenY + 2, w - 16, h - 4);

      // Gate label
      ctx.fillStyle = 'rgba(200, 180, 120, 0.7)';
      ctx.font = '10px monospace';
      ctx.textAlign = 'center';
      ctx.fillText('⛩ Entrance', screenX + w / 2, screenY + h + 12);
    } else {
      // Closed — massive stone slab
      ctx.fillStyle = '#1a1a2e';
      ctx.fillRect(screenX, screenY, w, h);

      // Stone texture lines
      ctx.strokeStyle = '#2a2a3e';
      ctx.lineWidth = 1;
      for (let i = 1; i < entity.width; i++) {
        const lx = screenX + i * TILE_SIZE;
        ctx.beginPath();
        ctx.moveTo(lx, screenY);
        ctx.lineTo(lx, screenY + h);
        ctx.stroke();
      }

      // Glowing red cracks to show it's sealed
      ctx.strokeStyle = 'rgba(255, 60, 60, 0.4)';
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(screenX + w * 0.3, screenY);
      ctx.lineTo(screenX + w * 0.35, screenY + h);
      ctx.stroke();
      ctx.beginPath();
      ctx.moveTo(screenX + w * 0.7, screenY);
      ctx.lineTo(screenX + w * 0.65, screenY + h);
      ctx.stroke();

      // Label
      ctx.fillStyle = 'rgba(255, 80, 80, 0.8)';
      ctx.font = '10px monospace';
      ctx.textAlign = 'center';
      ctx.fillText('🔒 SEALED', screenX + w / 2, screenY + h + 12);
    }
  }
}
