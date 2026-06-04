// ============================================================
// GameCanvas — React component rendering the 4-layer canvas stack
// ============================================================

import { useRef, useEffect } from 'react';
import { CANVAS_WIDTH, CANVAS_HEIGHT } from '../engine/types';
import type { GameEngine } from '../engine/GameEngine';

interface GameCanvasProps {
  engineRef: React.MutableRefObject<GameEngine | null>;
}

export function GameCanvas({ engineRef }: GameCanvasProps) {
  const baseMapRef = useRef<HTMLCanvasElement>(null);
  const paintRef = useRef<HTMLCanvasElement>(null);
  const entityRef = useRef<HTMLCanvasElement>(null);
  const vfxRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    if (
      !baseMapRef.current ||
      !paintRef.current ||
      !entityRef.current ||
      !vfxRef.current ||
      !engineRef.current
    ) return;

    // Bind all 4 canvases to the engine
    engineRef.current.setCanvasRefs({
      baseMap: baseMapRef.current,
      paint: paintRef.current,
      entity: entityRef.current,
      vfx: vfxRef.current,
    });

    // Start the game loop
    engineRef.current.start();

    return () => {
      engineRef.current?.stop();
    };
  }, [engineRef]);

  const canvasStyle: React.CSSProperties = {
    position: 'absolute',
    top: 0,
    left: 0,
    imageRendering: 'pixelated', // crisp pixel art rendering
  };

  return (
    <div
      className="game-canvas-container"
      style={{
        position: 'relative',
        width: CANVAS_WIDTH,
        height: CANVAS_HEIGHT,
        overflow: 'hidden',
        border: '3px solid #333',
        borderRadius: '4px',
        background: '#000',
      }}
    >
      {/* Layer 0: Base Map (Static) */}
      <canvas
        ref={baseMapRef}
        className="game-layer"
        width={CANVAS_WIDTH}
        height={CANVAS_HEIGHT}
        style={{ ...canvasStyle, zIndex: 0 }}
      />

      {/* Layer 1: Paint Layer (Persistent AI marks) */}
      <canvas
        ref={paintRef}
        className="game-layer"
        width={CANVAS_WIDTH}
        height={CANVAS_HEIGHT}
        style={{ ...canvasStyle, zIndex: 1 }}
      />

      {/* Layer 2: Entity Layer (Sprites, cleared each frame) */}
      <canvas
        ref={entityRef}
        className="game-layer"
        width={CANVAS_WIDTH}
        height={CANVAS_HEIGHT}
        style={{ ...canvasStyle, zIndex: 2 }}
      />

      {/* Layer 3: VFX Layer (AI animations, cleared each frame) */}
      <canvas
        ref={vfxRef}
        className="game-layer"
        width={CANVAS_WIDTH}
        height={CANVAS_HEIGHT}
        style={{ ...canvasStyle, zIndex: 3 }}
      />
    </div>
  );
}
