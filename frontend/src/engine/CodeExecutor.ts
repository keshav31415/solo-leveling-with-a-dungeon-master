// ============================================================
// CodeExecutor — Safely runs AI-generated JavaScript
// ============================================================

import { GameAPI } from './GameAPI';

export class CodeExecutor {
  private gameAPI: GameAPI;

  constructor(gameAPI: GameAPI) {
    this.gameAPI = gameAPI;
  }

  /**
   * Execute AI-generated JavaScript code string.
   * 
   * The code is wrapped in a `new Function()` call and given access to:
   * - `GameAPI`: The game API for entity/context access
   * - `ctx`: Alias for GameAPI.getVFXCtx() (convenience for the AI)
   * - `requestAnimationFrame`: For animation loops
   * - `Math`, `console`: Standard JS utilities
   * 
   * The AI does NOT have access to `window`, `document`, `fetch`, etc.
   */
  // Max frames any single injection is allowed to run (~5s at 60fps).
  // Each execute() call gets its own counter so animations don't share budgets.
  private static readonly FRAME_LIMIT = 300;

  execute(jsCodeString: string): { success: boolean; error?: string } {
    try {
      // Per-injection frame counter — prevents runaway requestAnimationFrame loops.
      let frameCount = 0;
      const limitedRAF = (callback: FrameRequestCallback): number => {
        if (frameCount >= CodeExecutor.FRAME_LIMIT) {
          console.warn(
            `[CodeExecutor] Animation auto-terminated after ${CodeExecutor.FRAME_LIMIT} frames.`
          );
          return 0;
        }
        frameCount++;
        return window.requestAnimationFrame(callback);
      };

      const fn = new Function(
        'GameAPI',
        'ctx',
        'paintCtx',
        'requestAnimationFrame',
        'cancelAnimationFrame',
        'Math',
        'console',
        'setTimeout',
        'clearTimeout',
        jsCodeString
      );

      fn(
        this.gameAPI,
        this.gameAPI.getVFXCtx(),
        this.gameAPI.getPaintCtx(),
        limitedRAF,
        window.cancelAnimationFrame.bind(window),
        Math,
        console,
        window.setTimeout.bind(window),
        window.clearTimeout.bind(window)
      );

      return { success: true };
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : String(error);
      console.error('[CodeExecutor] AI code execution failed:', errorMessage);
      console.error('[CodeExecutor] Failed code:', jsCodeString);
      return { success: false, error: errorMessage };
    }
  }
}
