// ============================================================
// GameEngine — The main game loop that ties everything together
// ============================================================

import { CANVAS_WIDTH, CANVAS_HEIGHT } from './types';
import { TileMap } from './TileMap';
import { Camera } from './Camera';
import { EntityManager } from './EntityManager';
import { InputHandler } from './InputHandler';
import { GameAPI } from './GameAPI';
import { CodeExecutor } from './CodeExecutor';
import { TriggerManager } from './TriggerManager';
import { Pathfinder } from './Pathfinder';
import { NPCMovementSystem } from './NPCMovementSystem';
import type { EntityData, TileMapData } from './types';

export interface GameCanvasRefs {
  baseMap: HTMLCanvasElement;    // Layer 0
  paint: HTMLCanvasElement;     // Layer 1
  entity: HTMLCanvasElement;    // Layer 2
  vfx: HTMLCanvasElement;       // Layer 3
}

export type DialogueCallback = (narrative: string, speaker?: string) => void;
export type InteractCallback = (target: EntityData) => void;
export type TriggerEventCallback = (eventName: string) => void;

export class GameEngine {
  private tileMap: TileMap;
  private camera: Camera;
  private entityManager: EntityManager;
  private inputHandler: InputHandler;
  private gameAPI: GameAPI;
  private codeExecutor: CodeExecutor;
  private triggerManager: TriggerManager;
  private pathfinder: Pathfinder;
  private npcMovement: NPCMovementSystem;

  private _canvasRefs: GameCanvasRefs | null = null;
  private contexts: {
    baseMap: CanvasRenderingContext2D;
    paint: CanvasRenderingContext2D;
    entity: CanvasRenderingContext2D;
    vfx: CanvasRenderingContext2D;
  } | null = null;

  private animationFrameId: number | null = null;
  private isRunning: boolean = false;
  private moveCooldown: number = 0;
  private readonly MOVE_COOLDOWN_FRAMES = 16; // frames between moves (~267ms at 60fps)
  private inputLocked: boolean = false; // true when dialogue box is open

  private offscreenPaintCanvas: HTMLCanvasElement | null = null;
  private offscreenPaintCtx: CanvasRenderingContext2D | null = null;

  // Callbacks to React
  private onDialogue: DialogueCallback | null = null;
  private onInteract: InteractCallback | null = null;
  private _onTriggerEvent: TriggerEventCallback | null = null;

  // Action tracking for triggers
  private actionsTaken: number = 0;
  private itemsInspected: Set<string> = new Set();
  private entitiesSpokenTo: Set<string> = new Set();

  constructor(mapData: TileMapData, entities: EntityData[]) {
    this.tileMap = new TileMap(mapData);
    this.camera = new Camera(
      this.tileMap.getPixelWidth(),
      this.tileMap.getPixelHeight()
    );
    this.entityManager = new EntityManager(entities, this.tileMap);
    this.inputHandler = new InputHandler();
    this.pathfinder = new Pathfinder(this.tileMap);
    this.npcMovement = new NPCMovementSystem(this.entityManager, this.pathfinder);
    this.gameAPI = new GameAPI(this.entityManager, this.npcMovement);
    this.codeExecutor = new CodeExecutor(this.gameAPI);
    this.triggerManager = new TriggerManager(this);

    // Snap camera to player immediately
    const player = this.entityManager.getPlayer();
    if (player) {
      this.camera.snapTo(player);
    }

    // Expose GameAPI globally for AI code
    (window as any).GameAPI = this.gameAPI;
  }

  /** Bind canvas elements from React */
  setCanvasRefs(refs: GameCanvasRefs) {
    this.canvasRefs = refs;
    this.contexts = {
      baseMap: refs.baseMap.getContext('2d')!,
      paint: refs.paint.getContext('2d')!,
      entity: refs.entity.getContext('2d')!,
      vfx: refs.vfx.getContext('2d')!,
    };

    // Create world-sized offscreen canvas for persistent marks
    if (!this.offscreenPaintCanvas) {
      this.offscreenPaintCanvas = document.createElement('canvas');
      this.offscreenPaintCanvas.width = this.tileMap.getPixelWidth();
      this.offscreenPaintCanvas.height = this.tileMap.getPixelHeight();
      this.offscreenPaintCtx = this.offscreenPaintCanvas.getContext('2d')!;
    }

    // Update GameAPI with the canvas contexts
    this.gameAPI.setContexts(this.contexts.vfx, this.offscreenPaintCtx!);
  }

  /** Register dialogue callback (for showing text in UI) */
  setDialogueCallback(cb: DialogueCallback) {
    this.onDialogue = cb;
  }

  /** Lock/unlock input (used when dialogue is showing) */
  setInputLocked(locked: boolean) {
    this.inputLocked = locked;
  }

  /** Register interact callback (for when player presses interact near an NPC) */
  setInteractCallback(cb: InteractCallback) {
    this.onInteract = cb;
  }

  /** Start the game loop */
  start() {
    if (this.isRunning) return;
    this.isRunning = true;
    this.gameLoop();
  }

  /** Stop the game loop */
  stop() {
    this.isRunning = false;
    if (this.animationFrameId) {
      cancelAnimationFrame(this.animationFrameId);
      this.animationFrameId = null;
    }
  }

  /** Execute AI-generated JavaScript code */
  executeAICode(jsCode: string) {
    return this.codeExecutor.execute(jsCode);
  }

  /** Show a narrative message */
  showNarrative(text: string, speaker?: string) {
    if (this.onDialogue) {
      this.onDialogue(text, speaker);
    }
  }

  /** Get tracking data for triggers */
  getTrackingData() {
    return {
      actionsTaken: this.actionsTaken,
      itemsInspected: Array.from(this.itemsInspected),
      entitiesSpokenTo: Array.from(this.entitiesSpokenTo),
    };
  }

  /** Get the EntityManager (for building AI payloads) */
  getEntityManager(): EntityManager {
    return this.entityManager;
  }

  /** Get the GameAPI instance */
  getGameAPI(): GameAPI {
    return this.gameAPI;
  }

  /** Get the TriggerManager instance */
  getTriggerManager(): TriggerManager {
    return this.triggerManager;
  }

  /** Get the NPCMovementSystem instance */
  getNPCMovementSystem(): NPCMovementSystem {
    return this.npcMovement;
  }

  /** Register trigger event callback */
  setTriggerEventCallback(cb: TriggerEventCallback) {
    this.onTriggerEvent = cb;
  }

  // --- The Main Game Loop ---

  private gameLoop = () => {
    if (!this.isRunning || !this.contexts) return;

    this.update();
    this.render();

    this.inputHandler.clearFrameState();
    this.animationFrameId = requestAnimationFrame(this.gameLoop);
  };

  private update() {
    // Handle player movement
    if (this.moveCooldown > 0) {
      this.moveCooldown--;
    } else {
      const dir = this.inputHandler.getMovementDirection();
      if (dir) {
        const player = this.entityManager.getPlayer();
        if (player) {
          const moved = this.entityManager.tryMove(player.id, dir.dx, dir.dy);
          if (moved) {
            this.moveCooldown = this.MOVE_COOLDOWN_FRAMES;
            this.actionsTaken++;
          }
        }
      }
    }

    // Handle interaction (skip if input is locked, e.g. dialogue open)
    if (!this.inputLocked && this.inputHandler.isInteractPressed()) {
      const target = this.entityManager.getInteractableNearPlayer();
      if (target) {
        this.entitiesSpokenTo.add(target.id);
        this.itemsInspected.add(target.id);
        this.actionsTaken++;
        if (this.onInteract) {
          this.onInteract(target);
        }
      }
    }

    // Update NPC autonomous movement
    this.npcMovement.update();

    // Update entity smooth movement
    this.entityManager.update();

    // Update camera to follow player
    const player = this.entityManager.getPlayer();
    if (player) {
      this.camera.follow(player);
    }

    // Update GameAPI with current camera offset
    this.gameAPI.setCameraOffset(this.camera.x, this.camera.y);
    if (this.contexts) {
      this.gameAPI.setContexts(this.contexts.vfx, this.contexts.paint);
    }

    // Evaluate triggers
    this.triggerManager.evaluate(this.getTrackingData());
  }

  private render() {
    if (!this.contexts) return;

    const camX = this.camera.x;
    const camY = this.camera.y;

    // Layer 0: Base Map (redraw visible portion)
    this.contexts.baseMap.clearRect(0, 0, CANVAS_WIDTH, CANVAS_HEIGHT);
    this.tileMap.render(this.contexts.baseMap, camX, camY, CANVAS_WIDTH, CANVAS_HEIGHT);

    // Layer 1: Paint Layer — Render visible portion from offscreen world canvas
    this.contexts.paint.clearRect(0, 0, CANVAS_WIDTH, CANVAS_HEIGHT);
    if (this.offscreenPaintCanvas) {
      this.contexts.paint.drawImage(
        this.offscreenPaintCanvas,
        camX, camY, CANVAS_WIDTH, CANVAS_HEIGHT, // source rect (from world)
        0, 0, CANVAS_WIDTH, CANVAS_HEIGHT // dest rect (to screen)
      );
    }

    // Layer 2: Entity Layer (cleared and redrawn every frame)
    this.contexts.entity.clearRect(0, 0, CANVAS_WIDTH, CANVAS_HEIGHT);
    this.entityManager.render(this.contexts.entity, camX, camY);

    // Layer 3: VFX Layer (cleared every frame, AI animations redraw themselves)
    this.contexts.vfx.clearRect(0, 0, CANVAS_WIDTH, CANVAS_HEIGHT);
    // AI animation loops using requestAnimationFrame will draw here
  }

  /** Cleanup */
  destroy() {
    this.stop();
    this.inputHandler.destroy();
    delete (window as any).GameAPI;
  }
}
