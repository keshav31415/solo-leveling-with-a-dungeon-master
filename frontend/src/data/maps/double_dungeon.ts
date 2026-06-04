// ============================================================
// Double Dungeon — Temple of Cartenon
// Circular arena with entrance corridor flanked by two giant
// guard statues. God Statue at the far north, gate at south.
// ============================================================

import type { TileMapData, EntityData } from '../../engine/types';

// Tile IDs
const F = 0; // Floor (dark stone)
const W = 1; // Wall
const G = 2; // Gate (entrance)
const S = 3; // Statue alcove (wall decoration)
const A = 4; // Altar platform
const C = 5; // Center floor rune pattern
const B = 6; // Blue flame torch

// Color palette
const TILE_COLORS: Record<number, string> = {
  [F]: '#1e1e36',
  [W]: '#0f0f1e',
  [G]: '#3d2b1a',
  [S]: '#1a1a35',
  [A]: '#252545',
  [C]: '#1a2040',
  [B]: '#1e2848',
};

// --- Map dimensions ---
// The circular hall is centered at (21, 21) with radius 18.
// Below the hall, a corridor extends from row 40 down to row 50.
// Total map: 42 wide x 56 tall (extra rows at bottom for gate visibility)
const MAP_W = 42;
const MAP_H = 56;
const CENTER_X = 21;
const CENTER_Y = 21;
const ROOM_RADIUS = 18;
const RUNE_RADIUS = 7;

// Corridor dimensions
const CORRIDOR_LEFT = CENTER_X - 4;   // 17
const CORRIDOR_RIGHT = CENTER_X + 4;  // 25
const CORRIDOR_START = CENTER_Y + ROOM_RADIUS; // 39 (where circle ends)
const CORRIDOR_END = MAP_H - 6;       // 50
const GATE_Y = CORRIDOR_END;          // door row

function generateMap(): { tiles: number[][]; collisions: number[][] } {
  const tiles: number[][] = Array.from({ length: MAP_H }, () =>
    Array(MAP_W).fill(W)
  );
  const collisions: number[][] = Array.from({ length: MAP_H }, () =>
    Array(MAP_W).fill(1)
  );

  // 1. Carve circular main hall
  for (let y = 0; y < MAP_H; y++) {
    for (let x = 0; x < MAP_W; x++) {
      const dx = x - CENTER_X;
      const dy = y - CENTER_Y;
      const dist = Math.sqrt(dx * dx + dy * dy);

      if (dist < ROOM_RADIUS) {
        tiles[y][x] = F;
        collisions[y][x] = 0;
      }

      if (dist < RUNE_RADIUS) {
        tiles[y][x] = C;
        collisions[y][x] = 0;
      }
    }
  }

  // 2. Altar platform at the north
  for (let y = CENTER_Y - ROOM_RADIUS + 1; y < CENTER_Y - ROOM_RADIUS + 5; y++) {
    for (let x = CENTER_X - 5; x <= CENTER_X + 5; x++) {
      if (tiles[y]?.[x] !== undefined && tiles[y][x] !== W) {
        tiles[y][x] = A;
        collisions[y][x] = 0;
      }
    }
  }

  // 3. Blue flame torches around inner perimeter
  for (let i = 0; i < 16; i++) {
    const angle = (i / 16) * Math.PI * 2;
    const tx = Math.round(CENTER_X + (ROOM_RADIUS - 1) * Math.cos(angle));
    const ty = Math.round(CENTER_Y + (ROOM_RADIUS - 1) * Math.sin(angle));
    if (tiles[ty]?.[tx] === F) {
      tiles[ty][tx] = B;
    }
  }

  // 4. Carve entrance corridor below the circle
  for (let y = CORRIDOR_START - 1; y <= CORRIDOR_END; y++) {
    for (let x = CORRIDOR_LEFT; x <= CORRIDOR_RIGHT; x++) {
      if (tiles[y]?.[x] !== undefined) {
        tiles[y][x] = F;
        collisions[y][x] = 0;
      }
    }
  }

  // 5. Torches along corridor walls
  for (let y = CORRIDOR_START + 1; y < CORRIDOR_END; y += 3) {
    if (tiles[y]?.[CORRIDOR_LEFT] !== undefined) {
      tiles[y][CORRIDOR_LEFT] = B;
    }
    if (tiles[y]?.[CORRIDOR_RIGHT] !== undefined) {
      tiles[y][CORRIDOR_RIGHT] = B;
    }
  }

  // 6. Gate at the very south end of the corridor
  const gateY = CORRIDOR_END;
  for (let x = CORRIDOR_LEFT + 1; x <= CORRIDOR_RIGHT - 1; x++) {
    if (tiles[gateY]?.[x] !== undefined) {
      tiles[gateY][x] = G;
      collisions[gateY][x] = 0;
    }
    if (tiles[gateY + 1]?.[x] !== undefined) {
      tiles[gateY + 1][x] = G;
      collisions[gateY + 1][x] = 0;
    }
  }

  return { tiles, collisions };
}

const { tiles: TILES, collisions: COLLISIONS } = generateMap();

export const DOUBLE_DUNGEON_MAP: TileMapData = {
  name: 'Double Dungeon - Temple of Cartenon',
  width: MAP_W,
  height: MAP_H,
  tiles: TILES,
  collisions: COLLISIONS,
  tileColors: TILE_COLORS,
};

// --- Entities ---

// Decorative statues in a circle around the hall
function generateStatueEntities(): EntityData[] {
  const statues: EntityData[] = [];
  const statueCount = 12;
  const statueRadius = ROOM_RADIUS - 3;

  for (let i = 0; i < statueCount; i++) {
    const angle = (i / statueCount) * Math.PI * 2 - Math.PI / 2;
    const gx = Math.round(CENTER_X + statueRadius * Math.cos(angle));
    const gy = Math.round(CENTER_Y + statueRadius * Math.sin(angle));

    if (gy < CENTER_Y - ROOM_RADIUS + 6) continue;
    if (gy > CENTER_Y + ROOM_RADIUS - 4) continue;

    statues.push({
      id: `statue_${i}`,
      label: 'Stone Statue',
      gridX: gx,
      gridY: gy,
      targetGridX: gx,
      targetGridY: gy,
      pixelX: 0,
      pixelY: 0,
      state: 'idle',
      direction: 'down',
      color: '#4a4a6a',
      outlineColor: '#2a2a4a',
      isPlayer: false,
      speed: 0,
      isMoving: false,
      isInteractable: false,
      width: 1,
      height: 1,
    });
  }
  return statues;
}

export const DOUBLE_DUNGEON_ENTITIES: EntityData[] = [
  // === PLAYER — starts mid-corridor ===
  {
    id: 'jinwoo',
    label: 'Sung Jinwoo',
    gridX: CENTER_X,
    gridY: CORRIDOR_END - 6,
    targetGridX: CENTER_X,
    targetGridY: CORRIDOR_END - 6,
    pixelX: 0,
    pixelY: 0,
    state: 'idle',
    direction: 'up',
    color: '#4a90d9',
    outlineColor: '#2563eb',
    isPlayer: true,
    speed: 2,
    isMoving: false,
    isInteractable: false,
    width: 1,
    height: 1,
  },

  // === NPCs — scattered in the corridor ===
  {
    id: 'joohee',
    label: 'Lee Joohee',
    gridX: CENTER_X + 2,
    gridY: CORRIDOR_END - 7,
    targetGridX: CENTER_X + 2,
    targetGridY: CORRIDOR_END - 7,
    pixelX: 0,
    pixelY: 0,
    state: 'idle',
    direction: 'up',
    color: '#e879a8',
    outlineColor: '#db2777',
    isPlayer: false,
    speed: 2,
    isMoving: false,
    isInteractable: true,
    width: 1,
    height: 1,
  },
  {
    id: 'song_chiyul',
    label: 'Song Chi-yul',
    gridX: CENTER_X - 2,
    gridY: CORRIDOR_END - 8,
    targetGridX: CENTER_X - 2,
    targetGridY: CORRIDOR_END - 8,
    pixelX: 0,
    pixelY: 0,
    state: 'idle',
    direction: 'right',
    color: '#f59e0b',
    outlineColor: '#d97706',
    isPlayer: false,
    speed: 2,
    isMoving: false,
    isInteractable: true,
    width: 1,
    height: 1,
  },
  {
    id: 'mr_park',
    label: 'Mr. Park',
    gridX: CENTER_X + 3,
    gridY: CORRIDOR_END - 9,
    targetGridX: CENTER_X + 3,
    targetGridY: CORRIDOR_END - 9,
    pixelX: 0,
    pixelY: 0,
    state: 'idle',
    direction: 'left',
    color: '#8b5cf6',
    outlineColor: '#7c3aed',
    isPlayer: false,
    speed: 2,
    isMoving: false,
    isInteractable: true,
    width: 1,
    height: 1,
  },
  {
    id: 'mr_kim',
    label: 'Mr. Kim',
    gridX: CENTER_X - 1,
    gridY: CORRIDOR_END - 5,
    targetGridX: CENTER_X - 1,
    targetGridY: CORRIDOR_END - 5,
    pixelX: 0,
    pixelY: 0,
    state: 'idle',
    direction: 'right',
    color: '#10b981',
    outlineColor: '#059669',
    isPlayer: false,
    speed: 2,
    isMoving: false,
    isInteractable: true,
    width: 1,
    height: 1,
  },

  // === TWO GIANT GUARD STATUES flanking the actual gate entrance ===
  {
    id: 'guard_statue_left',
    label: 'Guard Statue',
    gridX: CORRIDOR_LEFT - 1,
    gridY: GATE_Y - 1,
    targetGridX: CORRIDOR_LEFT - 1,
    targetGridY: GATE_Y - 1,
    pixelX: 0,
    pixelY: 0,
    state: 'idle',
    direction: 'right',
    color: '#5c5c7a',
    outlineColor: '#8b5cf6',
    isPlayer: false,
    speed: 0,
    isMoving: false,
    isInteractable: true,
    width: 2,
    height: 3,
  },
  {
    id: 'guard_statue_right',
    label: 'Guard Statue',
    gridX: CORRIDOR_RIGHT,
    gridY: GATE_Y - 1,
    targetGridX: CORRIDOR_RIGHT,
    targetGridY: GATE_Y - 1,
    pixelX: 0,
    pixelY: 0,
    state: 'idle',
    direction: 'left',
    color: '#5c5c7a',
    outlineColor: '#8b5cf6',
    isPlayer: false,
    speed: 0,
    isMoving: false,
    isInteractable: true,
    width: 2,
    height: 3,
  },

  // === ENTRANCE DOOR — can open/close ===
  {
    id: 'entrance_door',
    label: 'Dungeon Entrance',
    gridX: CORRIDOR_LEFT + 1,
    gridY: GATE_Y,
    targetGridX: CORRIDOR_LEFT + 1,
    targetGridY: GATE_Y,
    pixelX: 0,
    pixelY: 0,
    state: 'open',
    direction: 'down',
    color: '#3d2b1a',
    outlineColor: '#8b6914',
    isPlayer: false,
    speed: 0,
    isMoving: false,
    isInteractable: false,
    width: 7,
    height: 1,
  },

  // === GOD STATUE — far north of the circle (3x3) ===
  {
    id: 'giant_statue',
    label: 'God Statue',
    gridX: CENTER_X - 1,
    gridY: CENTER_Y - ROOM_RADIUS + 3,
    targetGridX: CENTER_X - 1,
    targetGridY: CENTER_Y - ROOM_RADIUS + 3,
    pixelX: 0,
    pixelY: 0,
    state: 'sleeping',
    direction: 'down',
    color: '#6b7280',
    outlineColor: '#ef4444',
    isPlayer: false,
    speed: 0,
    isMoving: false,
    isInteractable: true,
    width: 3,
    height: 3,
  },

  // === STONE TABLET — in front of the god statue ===
  {
    id: 'stone_tablet',
    label: 'Stone Tablet',
    gridX: CENTER_X,
    gridY: CENTER_Y - ROOM_RADIUS + 7,
    targetGridX: CENTER_X,
    targetGridY: CENTER_Y - ROOM_RADIUS + 7,
    pixelX: 0,
    pixelY: 0,
    state: 'idle',
    direction: 'down',
    color: '#94a3b8',
    outlineColor: '#c084fc',
    isPlayer: false,
    speed: 0,
    isMoving: false,
    isInteractable: true,
    width: 1,
    height: 1,
  },

  // === DECORATIVE STATUES in a ring ===
  ...generateStatueEntities(),
];
