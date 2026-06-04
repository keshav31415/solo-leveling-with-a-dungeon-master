// ============================================================
// Core Types for the Solo Leveling RPG Engine
// ============================================================

export const TILE_SIZE = 32;
export const VIEWPORT_COLS = 40;
export const VIEWPORT_ROWS = 25;
export const CANVAS_WIDTH = TILE_SIZE * VIEWPORT_COLS;  // 1280
export const CANVAS_HEIGHT = TILE_SIZE * VIEWPORT_ROWS; // 800

// --- Tile Map Types ---

export interface TileMapData {
  name: string;
  width: number;   // in tiles
  height: number;  // in tiles
  tiles: number[][]; // 2D array [row][col] of tile IDs
  collisions: number[][]; // 2D array [row][col], 1 = solid, 0 = walkable
  tileColors: Record<number, string>; // tile ID -> color (placeholder)
}

// --- Entity Types ---

export type Direction = 'up' | 'down' | 'left' | 'right';

export type EntityState =
  | 'idle'
  | 'walking'
  | 'attacking'
  | 'dead'
  | 'dead_ash'
  | 'panicking'
  | 'fleeing'
  | 'talking'
  | string; // allow AI to set custom states

export interface EntityData {
  id: string;
  label: string;          // display name (e.g., "Sung Jinwoo")
  gridX: number;          // current grid position
  gridY: number;
  targetGridX: number;    // where we're moving to (for smooth interpolation)
  targetGridY: number;
  pixelX: number;         // actual render position (smoothly interpolated)
  pixelY: number;
  state: EntityState;
  direction: Direction;
  color: string;          // placeholder color
  outlineColor: string;   // border color for the placeholder square
  isPlayer: boolean;      // true only for Jinwoo
  speed: number;          // pixels per frame for smooth movement
  isMoving: boolean;
  isInteractable: boolean;
  width: number;          // in tiles (most entities = 1)
  height: number;         // in tiles (giant statue might be 2x2)
}

// --- Camera Types ---

export interface CameraState {
  x: number;  // pixel offset of the camera's top-left corner
  y: number;
}

// --- NPC Movement Types ---

export type MovementBehavior = 'idle' | 'wander' | 'flee' | 'seek' | 'patrol' | 'battle'

export interface NPCMovementConfig {
  behavior: MovementBehavior
  stepCooldown?: number                         // frames between steps (default 12)
  homePosition?: { x: number; y: number }      // wander anchor
  wanderRadius?: number                         // max tiles from home (default 5)
  target?: string | { x: number; y: number }   // entity id or coords (seek / battle)
  fleeFrom?: string | { x: number; y: number } // entity id or coords (flee / battle)
  waypoints?: { x: number; y: number }[]       // ordered points (patrol)
  orbitRadius?: number                          // distance to maintain (battle)
}

// --- AI Response Types ---

export interface DMResponse {
  narrative: string;
  js_injection?: string;
  trigger_hit?: string | null;
  new_entity_states?: Record<string, EntityState>;
}

// --- Game State (sent to backend) ---

export interface VisualStatePayload {
  canvas_size: { width: number; height: number };
  entities: Array<{
    id: string;
    label: string;
    x: number;
    y: number;
    state: EntityState;
  }>;
  scene_id: string;
  current_event: string | null;
  recent_actions: string[];
}
