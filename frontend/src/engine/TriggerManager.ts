import type { GameEngine } from './GameEngine';

export type TriggerType = 'position' | 'action' | 'time';

export interface Trigger {
  id: string;
  type: TriggerType;
  condition: (engine: GameEngine, gameStateData: any) => boolean;
  onFire: () => void;
  fired: boolean;
}

export class TriggerManager {
  private triggers: Trigger[] = [];
  private engine: GameEngine;

  constructor(engine: GameEngine) {
    this.engine = engine;
  }

  addTrigger(trigger: Trigger) {
    this.triggers.push(trigger);
  }

  evaluate(gameStateData: any) {
    for (const t of this.triggers) {
      if (!t.fired && t.condition(this.engine, gameStateData)) {
        t.fired = true;
        t.onFire();
      }
    }
  }

  reset() {
    for (const t of this.triggers) {
      t.fired = false;
    }
  }
}
