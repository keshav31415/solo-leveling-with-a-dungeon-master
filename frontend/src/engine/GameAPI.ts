// ============================================================
// GameAPI — The API exposed to the AI's injected JavaScript
// ============================================================
// This is bound to window.GameAPI and passed into the AI's
// code sandbox. The AI uses this to find entities, access
// canvas contexts, and modify the game world.
// ============================================================

import type { EntityState, NPCMovementConfig } from './types';
import { EntityManager } from './EntityManager';
import type { NPCMovementSystem } from './NPCMovementSystem';

export class GameAPI {
  private entityManager: EntityManager;
  private npcMovement: NPCMovementSystem;
  private vfxCtx: CanvasRenderingContext2D | null = null;
  private paintCtx: CanvasRenderingContext2D | null = null;
  private cameraX: number = 0;
  private cameraY: number = 0;

  constructor(entityManager: EntityManager, npcMovement: NPCMovementSystem) {
    this.entityManager = entityManager;
    this.npcMovement = npcMovement;
  }

  /** Update the canvas contexts (called each frame by the engine) */
  setContexts(
    vfxCtx: CanvasRenderingContext2D,
    paintCtx: CanvasRenderingContext2D
  ) {
    this.vfxCtx = vfxCtx;
    this.paintCtx = paintCtx;
  }

  /** Update camera position (so AI code can convert grid -> screen coords) */
  setCameraOffset(x: number, y: number) {
    this.cameraX = x;
    this.cameraY = y;
  }

  // === Entity Access ===

  /** Get an entity by ID. Returns a safe copy with screen coordinates. */
  getEntity(id: string): {
    id: string;
    label: string;
    x: number;    // screen X
    y: number;    // screen Y
    gridX: number;
    gridY: number;
    state: EntityState;
    color: string;
    width: number;
    height: number;
  } | null {
    const entity = this.entityManager.getEntity(id);
    if (!entity) return null;

    return {
      id: entity.id,
      label: entity.label,
      x: entity.pixelX - this.cameraX,
      y: entity.pixelY - this.cameraY,
      gridX: entity.gridX,
      gridY: entity.gridY,
      state: entity.state,
      color: entity.color,
      width: entity.width,
      height: entity.height,
    };
  }

  /** Get all entity IDs */
  getAllEntityIds(): string[] {
    return this.entityManager.getAllEntities().map(e => e.id);
  }

  /** Set an entity's visual state */
  setEntityState(id: string, state: string) {
    this.entityManager.setEntityState(id, state);
  }

  /** Move an entity to a grid position (instant teleport) */
  moveEntity(id: string, gridX: number, gridY: number) {
    const entity = this.entityManager.getEntity(id);
    if (!entity) return;
    entity.gridX = gridX;
    entity.gridY = gridY;
    entity.targetGridX = gridX;
    entity.targetGridY = gridY;
    entity.pixelX = gridX * 32; // TILE_SIZE
    entity.pixelY = gridY * 32;
  }

  /** Change entity color */
  setEntityColor(id: string, color: string) {
    const entity = this.entityManager.getEntity(id);
    if (entity) entity.color = color;
  }

  // === NPC Movement Control ===

  /** Set an NPC's autonomous movement behavior (callable from JS injection) */
  setNPCMovement(entityId: string, config: NPCMovementConfig) {
    this.npcMovement.setMovement(entityId, config);
  }

  /** Stop an NPC's autonomous movement */
  clearNPCMovement(entityId: string) {
    this.npcMovement.clearMovement(entityId);
  }

  // === Canvas Context Access (for True Dynamic Code Injection) ===

  /** Get the VFX layer context (Layer 3 — temporary effects, cleared each frame) */
  getVFXCtx(): CanvasRenderingContext2D | null {
    return this.vfxCtx;
  }

  /** Get the Paint layer context (Layer 1 — persistent marks, never cleared) */
  getPaintCtx(): CanvasRenderingContext2D | null {
    return this.paintCtx;
  }

  // === Utility Helpers for AI ===

  /** Get camera offset so AI can calculate screen positions */
  getCameraOffset(): { x: number; y: number } {
    return { x: this.cameraX, y: this.cameraY };
  }

  /** Convert grid coordinates to screen pixel coordinates */
  gridToScreen(gridX: number, gridY: number): { x: number; y: number } {
    return {
      x: gridX * 32 - this.cameraX,
      y: gridY * 32 - this.cameraY,
    };
  }

  /** Get the tile size constant */
  getTileSize(): number {
    return 32;
  }

  // === Pre-built Helper Effects (convenience, but AI can also write raw ctx code) ===

  /** Shake the screen */
  shakeScreen(intensity: number = 5, durationMs: number = 300) {
    const canvases = document.querySelectorAll<HTMLCanvasElement>('.game-layer');
    const startTime = performance.now();

    const shake = () => {
      const elapsed = performance.now() - startTime;
      if (elapsed > durationMs) {
        // Reset positions
        canvases.forEach(c => {
          c.style.transform = 'translate(0, 0)';
        });
        return;
      }

      const progress = 1 - elapsed / durationMs;
      const offsetX = (Math.random() - 0.5) * intensity * progress;
      const offsetY = (Math.random() - 0.5) * intensity * progress;

      canvases.forEach(c => {
        c.style.transform = `translate(${offsetX}px, ${offsetY}px)`;
      });

      requestAnimationFrame(shake);
    };

    shake();
  }
}
