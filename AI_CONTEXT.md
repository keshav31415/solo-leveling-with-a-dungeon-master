# AI Context & Project Status
*This document serves as the central source of truth for the project. No matter which AI tool you are using (Antigravity, Cursor, Claude Code, Copilot), read this file to understand the architecture, progress, and next steps.*

## Project Overview
**Name:** Solo Leveling: The Double Dungeon
**Type:** 2D Retro RPG with LLM-powered Dungeon Master
**Tech Stack:**
- **Frontend:** React, TypeScript, Vite, Custom Canvas Engine (`GameEngine.ts`)
- **Backend:** Python, FastAPI, Groq API (LLM Integration)

## Core Architecture
- **GameEngine.ts**: Runs a 60fps loop, handles entity rendering, movement, collisions, and Triggers.
- **App.tsx**: The bridge between React UI and the Engine. Compiles `GameState` and sends it to the backend via `POST /api/action`.
- **Backend (`dm.py`, `llm.py`, `schemas.py`, `memory.py`)**: Receives action + state, builds a structured action-aware prompt using the memory system, calls Groq (fallback waterfall), validates via Pydantic, returns narrative/speaker/entity states/JS injection.

---

## What Has Been Built

### Map & Entities (`double_dungeon.ts`)
- Circular arena (radius 18) with entrance corridor
- NPCs: Lee Joohee, Song Chi-yul, Mr. Park, Mr. Kim
- Interactable objects: God Statue (`giant_statue`), Stone Tablet (`stone_tablet`), Entrance Door (`entrance_door`)
- Decorative statues in a ring around the hall

### Director Triggers (fire in this order)
1. `chamber_entered` — Auto-fires 800ms on game load. Narrates blue flames, no monsters, eerie confusion.
2. `joohee_terror` — Positional (`gridY < 30`). Joohee sees the God Statue's eyes move.
3. `commandments` — Action-based (fires when `stone_tablet` inspected). Narrates the three commandments.
4. `trap_springs` — Fires 1500ms after the player **dismisses** the commandments dialogue. Doors slam shut, screen shakes, entrance blocked via JS injection.

### Player Input (`PlayerInput.tsx`)
- Two rows: SAY (dialogue) + DO (action). Both optional. Both sent to backend.
- Combined into a single `jinwoo_turn` in the prompt: `says: "..." | *action*`.
- Uses `position: fixed` so it always pins to browser viewport bottom (canvas is 800px tall, viewports are shorter).
- `DialogueBox.tsx` also uses `position: fixed` for the same reason.

### Known Frontend Design Decisions
- `stone_tablet` first inspection skips the `interact` LLM call — owned entirely by the `commandments` trigger to avoid a race condition. Tracked via `firedTriggersRef` in `App.tsx`.
- `trap_springs` is chained via `pendingChainRef` in `App.tsx` — fires after the player dismisses the commandments dialogue, not on a raw timer.

---

## Memory & Fact System (`memory.py`, `schemas.py`)

### Three-Tier Architecture

**Level 1 — Runtime Memory** (active scene, persisted to `backend/memory.json`):
- `world_state`: dict of current scene reality (e.g. `entrance_door: closed`, `commandments_read: true`)
- `relationships`: per-NPC `{trust, fear, respect}` values (0–100)
- `knowledge`: list of facts the party currently knows
- `events_fired`: ordered list of director events that have fired
- `candidates`: memory candidates proposed by the DM, pending promotion
- `current_situation`: single authoritative situation string

**Level 2 — Scene Chronicle** (generated at scene end via LLM, archived permanently):
- `summary`, `major_events`, `relationship_changes`, `knowledge_gained`, `character_deaths`, `mysteries_revealed`

**Level 3 — Story Canon** (permanent, cross-scene facts promoted by the Director):
- Only facts that would still matter 10 scenes later
- Examples: "Jinwoo saved Joohee", "The commandments were revealed", "Song Chi-yul died"

**Ephemeral Dialogue Buffer** (in-memory only, never saved):
- Last 3 exchanges per NPC for immediate conversation continuity
- Cleared on server restart

### How Memory Is Used in Prompts

`director_event` prompt gets:
- `world_state`, `events_fired`, `knowledge`, `current_situation`

`interact` (NPC) prompt gets:
- `world_state`, `events_fired`, `knowledge`
- Relationship values for that NPC (trust/fear/respect)
- Story Canon facts
- Dialogue buffer (last 3 turns with this NPC)

### Memory Candidate Flow
- DM responses include `memory_candidates: [{fact, category, npc_involved}]`
- Categories: `world | relationship | knowledge | plot | death | mystery | quest`
- `knowledge` candidates are immediately added to `runtime.knowledge`
- All candidates accumulate in `runtime.candidates`
- At scene end (`POST /api/end_scene`): Director LLM reviews candidates and promotes to Story Canon

### World State Auto-Updates
Known side-effects applied automatically when director events fire:
- `chamber_entered` → `{chamber_entered: true}`
- `joohee_terror` → `{joohee_terror_occurred: true}`
- `commandments` → `{commandments_read: true}`
- `trap_springs` → `{entrance_door: "closed", trap_sprung: true}`

### API Endpoints
- `POST /api/action` — main game loop
- `POST /api/end_scene` — generate Chronicle, promote Canon, clear Runtime
- `POST /api/reset` — full memory wipe (new game)

### Backend Fallback Waterfall (`llm.py`)
`llama-3.3-70b-versatile` → `llama-3.1-8b-instant` → `gemma2-9b-it`

---

## Current State
- Full narrative sequence from entry to door-slam is playable end-to-end.
- Memory system is fully wired: world state, relationships, knowledge, candidates all update live.
- Player can walk around, talk to any NPC (SAY + DO), interact with objects, and experience all 4 triggers.
- `backend/memory.json` should be in `.gitignore` (contains playthrough data).

---

## Resume Metrics (MUST TRACK)
*These metrics must be measured and optimized. They will be showcased on the resume to demonstrate the quality of the system. Every AI tool working on this project should be aware of these and help instrument/measure them.*

### 1. Token Efficiency
- **What:** Compare prompt token count using the 3-tier memory system vs. a naive full-history baseline.
- **How to measure:** Log total tokens sent per LLM call. Run a full playthrough (50+ turns) under both approaches. Compute reduction %.
- **Target metric:** *"Reduced prompt token consumption by X% compared to full-history baseline while retaining contextual accuracy."*

### 2. Context Retention Accuracy
- **What:** After N conversation turns, can NPCs still recall specific facts planted earlier?
- **How to measure:** Build an automated test harness. Plant facts at specific turns (e.g., "Jinwoo tells Joohee a secret on turn 3"). Query the NPC about that fact at turns 10, 20, 50. Use an LLM-as-judge to score recall accuracy.
- **Target metric:** *"Achieved X% fact retention accuracy across 50+ conversation turns."*

### 3. Average Response Latency
- **What:** End-to-end time from player pressing Enter to dialogue appearing on screen.
- **How to measure:** Log timestamps at request-send and response-received in the frontend. Aggregate across 100+ interactions. Report median and p95.
- **Target metric:** *"Achieved Xms median end-to-end response latency for dynamic AI dialogue generation."*

### 4. Cost Per Play Session
- **What:** Total API cost for a complete playthrough (entry → door slam → combat → ending).
- **How to measure:** Track total input + output tokens consumed across an entire playthrough. Multiply by Groq's per-token pricing.
- **Target metric:** *"Full playthrough costs under $X.XX in API calls via optimized prompt compression."*

---

## Next Steps / Current Goals
*(Update this section whenever switching tools)*

1. **God Statue combat sequence**: After `trap_springs`, the scene needs its climax.
   - New triggers: statue awakens, first attack, hunter deaths
   - Combat/survival mechanics for Jinwoo
   - NPC deaths (entity state `dead_ash`, already supported by engine)
   - JS injection for statue movement and attack animations
   - The "prove your devotion" rule should be the key to survival

2. **Instrument the 4 resume metrics** (token efficiency, context retention, latency, cost).

3. ~~Add `backend/memory.json` to `.gitignore`~~ ✅ Done

