// ============================================================
// Camera — Follows the player with smooth lerping
// ============================================================

import { CANVAS_WIDTH, CANVAS_HEIGHT, TILE_SIZE } from './types';
import type { EntityData } from './types';

export class Camera {
  x: number = 0;
  y: number = 0;
  private mapPixelWidth: number;
  private mapPixelHeight: number;
  private lerpSpeed: number = 0.1; // smoothing factor (0 = no move, 1 = instant)

  constructor(mapPixelWidth: number, mapPixelHeight: number) {
    this.mapPixelWidth = mapPixelWidth;
    this.mapPixelHeight = mapPixelHeight;
  }

  /** Smoothly follow an entity */
  follow(entity: EntityData) {
    // Target: center the entity on screen
    const targetX = entity.pixelX + (TILE_SIZE * entity.width) / 2 - CANVAS_WIDTH / 2;
    const targetY = entity.pixelY + (TILE_SIZE * entity.height) / 2 - CANVAS_HEIGHT / 2;

    // Lerp towards target
    this.x += (targetX - this.x) * this.lerpSpeed;
    this.y += (targetY - this.y) * this.lerpSpeed;

    // Clamp so we don't show past the map edges
    this.x = Math.max(0, Math.min(this.x, this.mapPixelWidth - CANVAS_WIDTH));
    this.y = Math.max(0, Math.min(this.y, this.mapPixelHeight - CANVAS_HEIGHT));
  }

  /** Immediately snap camera to entity (used on initialization) */
  snapTo(entity: EntityData) {
    this.x = entity.pixelX + (TILE_SIZE * entity.width) / 2 - CANVAS_WIDTH / 2;
    this.y = entity.pixelY + (TILE_SIZE * entity.height) / 2 - CANVAS_HEIGHT / 2;

    this.x = Math.max(0, Math.min(this.x, this.mapPixelWidth - CANVAS_WIDTH));
    this.y = Math.max(0, Math.min(this.y, this.mapPixelHeight - CANVAS_HEIGHT));
  }
}
