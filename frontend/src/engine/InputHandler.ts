// ============================================================
// InputHandler — Keyboard input tracking
// ============================================================

type KeyCallback = () => void;

export class InputHandler {
  private keysDown: Set<string> = new Set();
  private keysJustPressed: Set<string> = new Set();
  private interactCallbacks: KeyCallback[] = [];

  constructor() {
    window.addEventListener('keydown', this.onKeyDown);
    window.addEventListener('keyup', this.onKeyUp);
  }

  private onKeyDown = (e: KeyboardEvent) => {
    // Don't intercept keys when the user is typing in an input field
    const activeEl = document.activeElement;
    if (activeEl && (activeEl.tagName === 'INPUT' || activeEl.tagName === 'TEXTAREA')) {
      return;
    }

    // Prevent default for game keys so page doesn't scroll
    const gameKeys = [
      'ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight',
      'w', 'a', 's', 'd', 'W', 'A', 'S', 'D',
      ' ', 'Enter', 'e', 'E'
    ];
    if (gameKeys.includes(e.key)) {
      e.preventDefault();
    }

    if (!this.keysDown.has(e.key)) {
      this.keysJustPressed.add(e.key);
    }
    this.keysDown.add(e.key);
  };

  private onKeyUp = (e: KeyboardEvent) => {
    this.keysDown.delete(e.key);
  };

  /** Returns true if key is currently held down */
  isKeyDown(key: string): boolean {
    return this.keysDown.has(key);
  }

  /** Returns true only on the first frame a key is pressed */
  wasKeyPressed(key: string): boolean {
    return this.keysJustPressed.has(key);
  }

  /** Check for movement direction (supports WASD and Arrow Keys) */
  getMovementDirection(): { dx: number; dy: number } | null {
    if (this.isKeyDown('ArrowUp') || this.isKeyDown('w') || this.isKeyDown('W')) {
      return { dx: 0, dy: -1 };
    }
    if (this.isKeyDown('ArrowDown') || this.isKeyDown('s') || this.isKeyDown('S')) {
      return { dx: 0, dy: 1 };
    }
    if (this.isKeyDown('ArrowLeft') || this.isKeyDown('a') || this.isKeyDown('A')) {
      return { dx: -1, dy: 0 };
    }
    if (this.isKeyDown('ArrowRight') || this.isKeyDown('d') || this.isKeyDown('D')) {
      return { dx: 1, dy: 0 };
    }
    return null;
  }

  /** Check if the interact key was just pressed (Space, Enter, or E) */
  isInteractPressed(): boolean {
    return (
      this.wasKeyPressed(' ') ||
      this.wasKeyPressed('Enter') ||
      this.wasKeyPressed('e') ||
      this.wasKeyPressed('E')
    );
  }

  /** Register callback for interact key */
  onInteract(callback: KeyCallback) {
    this.interactCallbacks.push(callback);
  }

  /** Must be called at the END of each game loop frame */
  clearFrameState() {
    this.keysJustPressed.clear();
  }

  /** Cleanup event listeners */
  destroy() {
    window.removeEventListener('keydown', this.onKeyDown);
    window.removeEventListener('keyup', this.onKeyUp);
  }
}
