import type { TileMap } from './TileMap';

export interface GridPos {
  x: number;
  y: number;
}

interface ANode {
  x:         number;
  y:         number;
  g:         number;       // cost from start
  h:         number;       // Manhattan distance to end
  f:         number;       // g + h
  parentKey: string | null;
}

const DIRS = [
  { dx:  0, dy: -1 },
  { dx:  0, dy:  1 },
  { dx: -1, dy:  0 },
  { dx:  1, dy:  0 },
];

const MAX_ITER = 2000; // hard limit — prevents hanging on large/complex searches

export class Pathfinder {
  private tileMap: TileMap;

  constructor(tileMap: TileMap) {
    this.tileMap = tileMap;
  }

  /**
   * Returns a path from (startX, startY) to (endX, endY) as an ordered list
   * of grid positions, excluding the start and including the end.
   * Returns [] if already at destination, target is unwalkable, or no path exists.
   */
  findPath(startX: number, startY: number, endX: number, endY: number): GridPos[] {
    if (startX === endX && startY === endY) return [];
    if (!this.tileMap.isWalkable(endX, endY))  return [];

    const key  = (x: number, y: number) => `${x},${y}`;
    const open = new Map<string, ANode>();
    const closed = new Set<string>();
    const all  = new Map<string, ANode>(); // all nodes ever created (for reconstruction)

    const start: ANode = {
      x: startX, y: startY,
      g: 0, h: this.h(startX, startY, endX, endY),
      f: 0, parentKey: null,
    };
    start.f = start.g + start.h;
    open.set(key(startX, startY), start);
    all.set(key(startX, startY), start);

    let iter = 0;

    while (open.size > 0 && iter++ < MAX_ITER) {
      // Pop node with lowest f (ties broken by lower h — prefers nodes closer to goal)
      let current: ANode | null = null;
      for (const node of open.values()) {
        if (!current || node.f < current.f || (node.f === current.f && node.h < current.h)) {
          current = node;
        }
      }
      if (!current) break;

      const ck = key(current.x, current.y);

      if (current.x === endX && current.y === endY) {
        return this.reconstruct(all, ck);
      }

      open.delete(ck);
      closed.add(ck);

      for (const { dx, dy } of DIRS) {
        const nx = current.x + dx;
        const ny = current.y + dy;
        const nk = key(nx, ny);

        if (closed.has(nk))                   continue;
        if (!this.tileMap.isWalkable(nx, ny)) continue;

        const g = current.g + 1;
        const existing = open.get(nk);
        if (existing && existing.g <= g)      continue;

        const node: ANode = {
          x: nx, y: ny,
          g,
          h: this.h(nx, ny, endX, endY),
          f: g + this.h(nx, ny, endX, endY),
          parentKey: ck,
        };
        open.set(nk, node);
        all.set(nk, node);
      }
    }

    return [];
  }

  private h(x1: number, y1: number, x2: number, y2: number): number {
    return Math.abs(x2 - x1) + Math.abs(y2 - y1);
  }

  private reconstruct(all: Map<string, ANode>, endKey: string): GridPos[] {
    const path: GridPos[] = [];
    let node = all.get(endKey);
    while (node && node.parentKey !== null) {
      path.unshift({ x: node.x, y: node.y });
      node = all.get(node.parentKey);
    }
    return path;
  }
}
