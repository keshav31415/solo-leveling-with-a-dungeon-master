// ============================================================
// App.tsx — Main Application Entry Point
// ============================================================

import { useRef, useEffect, useState, useCallback } from 'react';
import { GameCanvas } from './components/GameCanvas';
import { DialogueBox } from './components/DialogueBox';
import { PlayerInput } from './components/PlayerInput';
import { GameEngine } from './engine/GameEngine';
import { DOUBLE_DUNGEON_MAP, DOUBLE_DUNGEON_ENTITIES } from './data/maps/double_dungeon';
import { CANVAS_WIDTH, CANVAS_HEIGHT } from './engine/types';
import type { EntityData, NPCMovementConfig } from './engine/types';
import './App.css';

const API_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000';

// IDs of entities that are inanimate objects (not NPCs you "talk" to)
const INANIMATE_ENTITIES = new Set([
  'giant_statue', 'stone_tablet', 'guard_statue_left', 'guard_statue_right',
  'entrance_door',
]);

// Check if an entity ID is a decorative statue (generated procedurally)
function isInanimateEntity(id: string): boolean {
  return INANIMATE_ENTITIES.has(id) || id.startsWith('statue_');
}

function App() {
  const engineRef = useRef<GameEngine | null>(null);
  const [engineReady, setEngineReady] = useState(false);

  // Dialogue state
  const [dialogue, setDialogue] = useState<{
    text: string;
    speaker?: string;
    isVisible: boolean;
  }>({ text: '', speaker: undefined, isVisible: false });

  // Player input state (for typing messages to NPCs)
  const [playerInput, setPlayerInput] = useState<{
    isVisible: boolean;
    target: EntityData | null;
  }>({ isVisible: false, target: null });

  // Event history to send to AI
  const [eventHistory, setEventHistory] = useState<string[]>([]);

  // Tracks which director triggers have already fired (to prevent interact/trigger race conditions)
  const firedTriggersRef = useRef<Set<string>>(new Set());

  // When a director event wants to chain into another event after the player dismisses dialogue
  const pendingChainRef = useRef<string | null>(null);

  // Scene State
  const [currentSituation, setCurrentSituation] = useState(
    "Blue flames have spontaneously lit up the perimeter of the massive, ancient temple. There are no monsters in sight. The hunters are scattered, inspecting the room in confusion."
  );
  const [itemsInspected, setItemsInspected] = useState<Set<string>>(new Set());

  // Create engine and setup callbacks
  useEffect(() => {
    // Treat every page load as a fresh game — backend memory resets to match frontend state
    fetch(`${API_URL}/api/reset`, { method: 'POST' }).catch(() => {});

    const engine = new GameEngine(
      DOUBLE_DUNGEON_MAP,
      JSON.parse(JSON.stringify(DOUBLE_DUNGEON_ENTITIES))
    );
    engineRef.current = engine;
    setEngineReady(true);

    // Set dialogue callback
    engine.setDialogueCallback((narrative: string, speaker?: string) => {
      setDialogue({ text: narrative, speaker, isVisible: true });
    });

    // Set interact callback
    engine.setInteractCallback((target: EntityData) => {
      handleInteraction(target);
    });

    // Set trigger event callback
    engine.setTriggerEventCallback((eventName: string) => {
      handleDirectorEvent(eventName);
    });

    // --- Register Double Dungeon Triggers ---
    const triggerManager = engine.getTriggerManager();

    // Trigger 1: Joohee's Terror (Player walks to the middle of the room — approaching the statue)
    triggerManager.addTrigger({
      id: 'joohee_terror',
      type: 'position',
      fired: false,
      condition: (_eng) => {
        const player = engineRef.current?.getEntityManager().getPlayer();
        return player != null && player.gridY < 30;
      },
      onFire: () => handleDirectorEvent('joohee_terror')
    });

    // Trigger 2: The Commandments (Player interacts with stone tablet)
    triggerManager.addTrigger({
      id: 'commandments',
      type: 'action',
      fired: false,
      condition: (_eng, state) => {
        return state.itemsInspected.includes('stone_tablet');
      },
      onFire: () => handleDirectorEvent('commandments')
    });

    // Fire chamber_entered immediately — the party just stepped into the dungeon
    setTimeout(() => handleDirectorEvent('chamber_entered'), 800);

    return () => {
      engine.destroy();
      engineRef.current = null;
      setEngineReady(false);
    };
  }, []);

  // Apply NPC movement directives from DM response
  const applyMovementDirectives = useCallback((directives: any[]) => {
    if (!engineRef.current || !directives?.length) return;
    const api = engineRef.current.getGameAPI();
    for (const d of directives) {
      const config: NPCMovementConfig = {
        behavior:     d.behavior,
        stepCooldown: d.step_cooldown,
        target:       d.target,
        fleeFrom:     d.flee_from,
        wanderRadius: d.wander_radius,
        orbitRadius:  d.orbit_radius,
        waypoints:    d.waypoints,
      };
      api.setNPCMovement(d.npc_id, config);
    }
  }, []);

  // Compile current game state to send to backend
  const getGameState = useCallback(() => {
    if (!engineRef.current) return null;
    const em = engineRef.current.getEntityManager();
    const entities = em.getAllEntities();
    
    const entity_states: Record<string, any> = {};
    entities.forEach(ent => {
      entity_states[ent.id] = {
        id: ent.id,
        label: ent.label,
        gridX: ent.gridX,
        gridY: ent.gridY,
        state: ent.state,
      };
    });

    const tracking = engineRef.current.getTrackingData();

    return {
      scene_id: 'double_dungeon',
      player_stats: {
        name: 'Sung Jinwoo',
        rank: 'E-Rank',
        hp: 100,
        actions_taken: tracking.actionsTaken,
        items_inspected: tracking.itemsInspected,
        entities_spoken_to: tracking.entitiesSpokenTo,
      },
      entity_states,
      event_queue: [],
      scene_state: {
        current_situation: currentSituation
      },
      sandbox_tracking: {
        items_inspected: Array.from(itemsInspected),
        player_coordinates: engineRef.current.getEntityManager().getPlayer() 
          ? { x: engineRef.current.getEntityManager().getPlayer()!.gridX, y: engineRef.current.getEntityManager().getPlayer()!.gridY } 
          : { x: 0, y: 0 }
      },
      recent_history: eventHistory.slice(-5), // only send last 5 events
    };
  }, [eventHistory, currentSituation, itemsInspected]);

  // Handle director events (automated scene events)
  const handleDirectorEvent = useCallback(async (eventName: string) => {
    if (!engineRef.current) return;

    firedTriggersRef.current.add(eventName);
    engineRef.current.setInputLocked(true);
    setDialogue({ text: '...', speaker: 'NARRATOR', isVisible: true });

    const gameState = getGameState();
    if (!gameState) return;

    try {
      const response = await fetch(`${API_URL}/api/action`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          action: { action_type: 'director_event', target: eventName, context: {} },
          state: gameState
        })
      });

      if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);

      const data = await response.json();
      
      const finalNarrative = data.narrative || `Event: ${eventName}`;
      const finalSpeaker = data.speaker || 'NARRATOR';
      
      setDialogue({ text: finalNarrative, speaker: finalSpeaker, isVisible: true });
      setEventHistory(prev => [...prev, `[EVENT] ${finalSpeaker}: ${finalNarrative}`]);

      if (data.js_injection) {
        try { engineRef.current.executeAICode(data.js_injection); }
        catch (err) { console.error("Error executing JS injection:", err); }
      }

      applyMovementDirectives(data.npc_movement_directives);

      if (data.new_situation) {
        setCurrentSituation(data.new_situation);
      }

      // Queue trap_springs to fire after the player dismisses this dialogue
      if (eventName === 'commandments') {
        pendingChainRef.current = 'trap_springs';
      }

    } catch (error) {
      console.error("Failed to execute director event:", error);
    }
  }, [getGameState]);

  // Handle interaction with entities
  const handleInteraction = useCallback(async (target: EntityData) => {
    if (!engineRef.current) return;

    // stone_tablet's first inspection is owned by the commandments director trigger —
    // skip the interact LLM call so both don't race to set the dialogue.
    if (target.id === 'stone_tablet' && !firedTriggersRef.current.has('commandments')) {
      engineRef.current.setInputLocked(true);
      setDialogue({ text: '...', speaker: 'NARRATOR', isVisible: true });
      return;
    }

    // If the target is an inanimate object, send directly to the AI (no player input needed)
    if (isInanimateEntity(target.id)) {
      await sendInteraction(target, '');
      return;
    }

    // For NPCs, show the player input box so they can type what they want to say
    engineRef.current.setInputLocked(true);
    setPlayerInput({ isVisible: true, target });
  }, []);

  // Send the actual interaction request to the backend
  const sendInteraction = useCallback(async (target: EntityData, playerMessage: string, playerAction: string = '') => {
    if (!engineRef.current) return;

    // Lock input and show loading
    engineRef.current.setInputLocked(true);
    setPlayerInput({ isVisible: false, target: null });
    setDialogue({
      text: '...',
      speaker: isInanimateEntity(target.id) ? 'NARRATOR' : target.label,
      isVisible: true
    });

    // Track sandbox inspection
    setItemsInspected(prev => new Set(prev).add(target.id));

    const gameState = getGameState();
    if (!gameState) return;

    try {
      const response = await fetch(`${API_URL}/api/action`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          action: {
            action_type: 'interact',
            target: target.id,
            context: { player_message: playerMessage, player_action: playerAction }
          },
          state: gameState
        })
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      
      // Update dialogue
      const finalNarrative = data.narrative || `You inspect the ${target.label}.`;
      const finalSpeaker = data.speaker || (isInanimateEntity(target.id) ? 'NARRATOR' : target.label);
      setDialogue({
        text: finalNarrative,
        speaker: finalSpeaker,
        isVisible: true
      });

      // Store both sides of the conversation so the LLM has proper context next turn
      const historyEntries: string[] = [];
      if (!isInanimateEntity(target.id)) {
        const parts: string[] = [];
        if (playerMessage) parts.push(`says: "${playerMessage}"`);
        if (playerAction) parts.push(`*${playerAction}*`);
        if (parts.length) historyEntries.push(`[Jinwoo → ${finalSpeaker}]: ${parts.join(' | ')}`);
      }
      historyEntries.push(`[${finalSpeaker}]: ${finalNarrative}`);
      setEventHistory(prev => [...prev, ...historyEntries]);

      // Update entity states in engine if returned
      if (data.new_state && data.new_state.entity_states) {
        const engine = engineRef.current;
        Object.entries(data.new_state.entity_states).forEach(([entityId, entData]: [string, any]) => {
          if (entData.state) {
            engine.getGameAPI().setEntityState(entityId, entData.state);
          }
        });
      }

      if (data.new_situation) {
        setCurrentSituation(data.new_situation);
      }

      // Execute JS injection
      if (data.js_injection) {
        try {
          engineRef.current.executeAICode(data.js_injection);
        } catch (err) {
          console.error("Error executing JS injection:", err);
        }
      }

      applyMovementDirectives(data.npc_movement_directives);

    } catch (error) {
      console.error("Failed to connect to DM backend:", error);
      
      // Fallback
      const messages: Record<string, string> = {
        joohee: "Jinwoo... this place gives me the creeps. I have a bad feeling about this.",
        song_chiyul: "Everyone stay close. We don't know what's in here. Let's explore carefully.",
        mr_park: "Did you see the size of that statue? I've never seen anything like it in a D-rank dungeon...",
        mr_kim: "Something feels off. The mana density here is way too high for a D-rank.",
        giant_statue: "You look up at the massive stone figure. Its eyes are closed, but you can't shake the feeling that it's watching you...",
      };
      const text = messages[target.id] || `You inspect the ${target.label}.`;
      setDialogue({
        text: text + " (DM Offline)",
        speaker: isInanimateEntity(target.id) ? 'NARRATOR' : target.label,
        isVisible: true
      });
    }
  }, [getGameState]);

  // Handle player submitting typed message/action to NPC
  const handlePlayerInputSubmit = useCallback((message: string, action: string) => {
    if (!playerInput.target) return;
    sendInteraction(playerInput.target, message, action);
  }, [playerInput.target, sendInteraction]);

  // Handle player cancelling the input
  const handlePlayerInputCancel = useCallback(() => {
    setPlayerInput({ isVisible: false, target: null });
    setTimeout(() => {
      engineRef.current?.setInputLocked(false);
    }, 100);
  }, []);

  // Dismiss dialogue
  const handleDismissDialogue = useCallback(() => {
    setDialogue(prev => ({ ...prev, isVisible: false }));

    const chained = pendingChainRef.current;
    pendingChainRef.current = null;

    if (chained) {
      // Fire the chained event after a short dramatic pause — doors slam after reading
      setTimeout(() => handleDirectorEvent(chained), 1500);
    } else {
      setTimeout(() => engineRef.current?.setInputLocked(false), 100);
    }
  }, [handleDirectorEvent]);

  // Test AI code injection (temporary dev button)
  const testCodeInjection = useCallback(() => {
    if (!engineRef.current) return;

    const testCode = `
      // Draw a red laser from the giant statue to mr_park
      const statue = GameAPI.getEntity('giant_statue');
      const target = GameAPI.getEntity('mr_park');
      if (!statue || !target) return;

      const vfx = GameAPI.getVFXCtx();
      if (!vfx) return;

      let frame = 0;
      const tileSize = GameAPI.getTileSize();
      const startX = statue.x + tileSize;
      const startY = statue.y + tileSize;
      const endX = target.x + tileSize / 2;
      const endY = target.y + tileSize / 2;

      function animate() {
        const vfxCtx = GameAPI.getVFXCtx();
        if (!vfxCtx) return;

        // Draw glowing laser beam
        vfxCtx.beginPath();
        vfxCtx.moveTo(startX, startY);
        vfxCtx.lineTo(endX, endY);
        vfxCtx.strokeStyle = 'rgba(255, 0, 0, ' + (1 - frame / 60) + ')';
        vfxCtx.lineWidth = 6 - (frame / 15);
        vfxCtx.shadowColor = 'red';
        vfxCtx.shadowBlur = 20;
        vfxCtx.stroke();

        // Inner bright core
        vfxCtx.beginPath();
        vfxCtx.moveTo(startX, startY);
        vfxCtx.lineTo(endX, endY);
        vfxCtx.strokeStyle = 'rgba(255, 200, 200, ' + (1 - frame / 60) + ')';
        vfxCtx.lineWidth = 2;
        vfxCtx.stroke();

        vfxCtx.shadowBlur = 0;

        if (frame < 60) {
          frame++;
          requestAnimationFrame(animate);
        } else {
      // Leave scorch mark on paint layer
      const paint = GameAPI.getPaintCtx();
      if (paint) {
        const cam = GameAPI.getCameraOffset();
        paint.fillStyle = 'rgba(40, 20, 10, 0.7)';
        paint.beginPath();
        paint.arc(endX + cam.x, endY + cam.y, 12, 0, Math.PI * 2);
        paint.fill();
      }

      // Kill the target
      GameAPI.setEntityState('mr_park', 'dead_ash');
      GameAPI.shakeScreen(8, 400);
    }
  }
  animate();
`;

    engineRef.current.executeAICode(testCode);
    const narrativeText = "The giant statue's eyes snap open, glowing a piercing crimson. A devastating beam of light shoots across the room, striking Mr. Park before he can react!";
    engineRef.current.showNarrative(narrativeText, 'NARRATOR');
    setEventHistory(prev => [...prev, `[EVENT] NARRATOR: ${narrativeText}`]);
  }, []);

  return (
    <div className="app-container">
      <header className="game-header">
        <h1>Solo Leveling — The Double Dungeon</h1>
      </header>

      <main className="game-main">
        <div
          className="game-viewport"
          style={{
            position: 'relative',
            width: CANVAS_WIDTH,
            height: CANVAS_HEIGHT,
          }}
        >
          {engineReady && <GameCanvas engineRef={engineRef} />}

          <DialogueBox
            text={dialogue.text}
            speaker={dialogue.speaker}
            isVisible={dialogue.isVisible}
            onDismiss={handleDismissDialogue}
          />

          <PlayerInput
            npcName={playerInput.target?.label || ''}
            isVisible={playerInput.isVisible}
            onSubmit={handlePlayerInputSubmit}
            onCancel={handlePlayerInputCancel}
          />
        </div>

        {/* Dev Controls (temporary) */}
        <div className="dev-controls">
          <button onClick={testCodeInjection} className="dev-btn">
            ⚡ Test: Laser Attack
          </button>
          <p className="dev-hint">
            WASD / Arrows to move • E / Space to interact
          </p>
        </div>
      </main>
    </div>
  );
}

export default App;
