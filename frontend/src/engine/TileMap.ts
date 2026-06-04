// ============================================================
// TileMap Renderer — Draws Layer 0 (Base Map)
// ============================================================

import { TILE_SIZE } from './types';
import type { TileMapData } from './types';

export class TileMap {
  private mapData: TileMapData;

  constructor(mapData: TileMapData) {
    this.mapData = mapData;
  }

  /** Get map dimensions in pixels */
  getPixelWidth(): number {
    return this.mapData.width * TILE_SIZE;
  }

  getPixelHeight(): number {
    return this.mapData.height * TILE_SIZE;
  }

  /** Check if a grid position is walkable */
  isWalkable(gridX: number, gridY: number): boolean {
    if (gridX < 0 || gridX >= this.mapData.width) return false;
    if (gridY < 0 || gridY >= this.mapData.height) return false;
    return this.mapData.collisions[gridY][gridX] === 0;
  }

  /** Get the tile ID at a grid position */
  getTileAt(gridX: number, gridY: number): number {
    if (gridX < 0 || gridX >= this.mapData.width) return -1;
    if (gridY < 0 || gridY >= this.mapData.height) return -1;
    return this.mapData.tiles[gridY][gridX];
  }

  /**
   * Render the entire base map to its canvas.
   * We render the full map once and then only re-render the visible
   * portion each frame using the camera offset.
   */
  render(ctx: CanvasRenderingContext2D, cameraX: number, cameraY: number, viewWidth: number, viewHeight: number) {
    // Calculate which tiles are visible
    const startCol = Math.max(0, Math.floor(cameraX / TILE_SIZE));
    const startRow = Math.max(0, Math.floor(cameraY / TILE_SIZE));
    const endCol = Math.min(this.mapData.width, Math.ceil((cameraX + viewWidth) / TILE_SIZE));
    const endRow = Math.min(this.mapData.height, Math.ceil((cameraY + viewHeight) / TILE_SIZE));

    for (let row = startRow; row < endRow; row++) {
      for (let col = startCol; col < endCol; col++) {
        const tileId = this.mapData.tiles[row][col];
        const color = this.mapData.tileColors[tileId] || '#ff00ff'; // magenta fallback

        const screenX = col * TILE_SIZE - cameraX;
        const screenY = row * TILE_SIZE - cameraY;

        // Draw the tile
        ctx.fillStyle = color;
        ctx.fillRect(screenX, screenY, TILE_SIZE, TILE_SIZE);

        // Draw subtle grid lines for the retro feel
        ctx.strokeStyle = 'rgba(255, 255, 255, 0.04)';
        ctx.lineWidth = 1;
        ctx.strokeRect(screenX, screenY, TILE_SIZE, TILE_SIZE);

        // Draw extra details for special tiles
        if (tileId === 3) {
          // Pillar — draw a circle on top
          ctx.fillStyle = 'rgba(100, 100, 140, 0.8)';
          ctx.beginPath();
          ctx.arc(
            screenX + TILE_SIZE / 2,
            screenY + TILE_SIZE / 2,
            TILE_SIZE / 3,
            0,
            Math.PI * 2
          );
          ctx.fill();
          ctx.strokeStyle = 'rgba(150, 150, 200, 0.5)';
          ctx.lineWidth = 2;
          ctx.stroke();
        }

        if (tileId === 4) {
          // Tablet — draw some "text" lines
          ctx.strokeStyle = 'rgba(180, 160, 120, 0.4)';
          ctx.lineWidth = 1;
          for (let i = 0; i < 3; i++) {
            const lineY = screenY + 8 + i * 8;
            ctx.beginPath();
            ctx.moveTo(screenX + 6, lineY);
            ctx.lineTo(screenX + TILE_SIZE - 6, lineY);
            ctx.stroke();
          }
        }
      }
    }
  }

  /** Dynamically update collision at a grid position */
  setCollision(gridX: number, gridY: number, value: number) {
    if (gridX >= 0 && gridX < this.mapData.width && gridY >= 0 && gridY < this.mapData.height) {
      this.mapData.collisions[gridY][gridX] = value;
    }
  }

  getMapData(): TileMapData {
    return this.mapData;
  }
}
