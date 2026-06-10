# Double Dungeon lore facts — seeded once into the lore_facts table on startup.
#
# tier:
#   mandatory   = always injected into the Director prompt for this scene (story beats)
#   structural  = injected when relevant entity/character is in play (rules + character profiles)
#   contextual  = future: retrieved via semantic search only
#
# temporal_status:
#   always_true    = never changes (commandment text, character personalities)
#   currently_true = true now, may be superseded by memory (door is open, no monsters visible)
#   was_true       = set automatically when a canon fact contradicts this

DOUBLE_DUNGEON_LORE = [
    # ── MANDATORY: always in Director prompt as required story beats ──────────────

    {
        "id": "dd_true_rank",
        "fact": "The Double Dungeon is secretly S-rank in true danger — disguised as a harmless D-rank dungeon from the outside",
        "category": "world",
        "scene_relevance": ["double_dungeon"],
        "characters_involved": [],
        "entities_involved": [],
        "tier": "mandatory",
        "temporal_status": "always_true",
    },
    {
        "id": "dd_trap_trigger",
        "fact": "Reading the stone tablet's commandments triggers the divine trap — the entrance doors seal immediately and permanently",
        "category": "rule",
        "scene_relevance": ["double_dungeon"],
        "characters_involved": [],
        "entities_involved": ["stone_tablet", "entrance_door"],
        "tier": "mandatory",
        "temporal_status": "always_true",
    },
    {
        "id": "dd_punishment",
        "fact": "Any soul that fails to abide by the commandments shall not leave this place alive — the God Statue enforces this without mercy",
        "category": "rule",
        "scene_relevance": ["double_dungeon"],
        "characters_involved": [],
        "entities_involved": ["giant_statue"],
        "tier": "mandatory",
        "temporal_status": "always_true",
    },
    {
        "id": "dd_devotion_key",
        "fact": "Following all three commandments — especially proving devotion to God — is the only key to surviving this dungeon",
        "category": "rule",
        "scene_relevance": ["double_dungeon"],
        "characters_involved": [],
        "entities_involved": ["giant_statue", "stone_tablet"],
        "tier": "mandatory",
        "temporal_status": "always_true",
    },

    # ── STRUCTURAL: world and rule facts injected when relevant entity is in play ─

    {
        "id": "dd_statue_eyes",
        "fact": "The God Statue's eyes track living beings — it is aware and watching at all times, not merely a stone idol",
        "category": "world",
        "scene_relevance": ["double_dungeon"],
        "characters_involved": [],
        "entities_involved": ["giant_statue"],
        "tier": "structural",
        "temporal_status": "always_true",
    },
    {
        "id": "dd_commandment_1",
        "fact": "First commandment carved on the stone tablet: 'Revere God'",
        "category": "rule",
        "scene_relevance": ["double_dungeon"],
        "characters_involved": [],
        "entities_involved": ["stone_tablet"],
        "tier": "structural",
        "temporal_status": "always_true",
    },
    {
        "id": "dd_commandment_2",
        "fact": "Second commandment carved on the stone tablet: 'Praise God'",
        "category": "rule",
        "scene_relevance": ["double_dungeon"],
        "characters_involved": [],
        "entities_involved": ["stone_tablet"],
        "tier": "structural",
        "temporal_status": "always_true",
    },
    {
        "id": "dd_commandment_3",
        "fact": "Third commandment carved on the stone tablet: 'Prove your devotion to God'",
        "category": "rule",
        "scene_relevance": ["double_dungeon"],
        "characters_involved": [],
        "entities_involved": ["stone_tablet"],
        "tier": "structural",
        "temporal_status": "always_true",
    },
    {
        "id": "dd_statue_attacks",
        "fact": "The God Statue will attack and kill anyone who breaks the commandments — it is the dungeon's judge and executioner",
        "category": "rule",
        "scene_relevance": ["double_dungeon"],
        "characters_involved": [],
        "entities_involved": ["giant_statue"],
        "tier": "structural",
        "temporal_status": "always_true",
    },
    {
        "id": "dd_no_monsters",
        "fact": "The chamber contains no conventional dungeon monsters — the statues themselves are the only threat",
        "category": "world",
        "scene_relevance": ["double_dungeon"],
        "characters_involved": [],
        "entities_involved": [],
        "tier": "structural",
        "temporal_status": "currently_true",
    },
    {
        "id": "dd_single_exit",
        "fact": "The entrance door is the only way in or out of the chamber",
        "category": "world",
        "scene_relevance": ["double_dungeon"],
        "characters_involved": [],
        "entities_involved": ["entrance_door"],
        "tier": "structural",
        "temporal_status": "always_true",
    },
    {
        "id": "dd_blue_flames",
        "fact": "Blue flames line the perimeter of the vast circular stone chamber",
        "category": "world",
        "scene_relevance": ["double_dungeon"],
        "characters_involved": [],
        "entities_involved": [],
        "tier": "structural",
        "temporal_status": "currently_true",
    },

    # ── STRUCTURAL: character profiles — always injected when NPC is addressed ────

    {
        "id": "char_joohee",
        "fact": "Lee Joohee is a B-rank healer who has known Jinwoo for a while. She is timid, easily frightened, and instinctively looks to Jinwoo for protection despite his E-rank status.",
        "category": "character",
        "scene_relevance": ["all"],
        "characters_involved": ["joohee"],
        "entities_involved": [],
        "tier": "structural",
        "temporal_status": "always_true",
    },
    {
        "id": "char_song_chiyul",
        "fact": "Song Chi-yul is the party leader — he projects calm authority but is clearly out of his depth and struggling to hold it together",
        "category": "character",
        "scene_relevance": ["all"],
        "characters_involved": ["song_chiyul"],
        "entities_involved": [],
        "tier": "structural",
        "temporal_status": "always_true",
    },
    {
        "id": "char_mr_park",
        "fact": "Mr. Park is a rough D-rank hunter who projects toughness but is secretly terrified — he masks fear with aggression and bravado",
        "category": "character",
        "scene_relevance": ["all"],
        "characters_involved": ["mr_park"],
        "entities_involved": [],
        "tier": "structural",
        "temporal_status": "always_true",
    },
    {
        "id": "char_mr_kim",
        "fact": "Mr. Kim is the most analytical member — he notices mana density, architectural anomalies, and inconsistencies that others miss",
        "category": "character",
        "scene_relevance": ["all"],
        "characters_involved": ["mr_kim"],
        "entities_involved": [],
        "tier": "structural",
        "temporal_status": "always_true",
    },
    {
        "id": "char_jinwoo",
        "fact": "Sung Jinwoo is officially E-rank, considered the weakest hunter in Korea — the rest of the party treats him as an unreliable burden",
        "category": "character",
        "scene_relevance": ["all"],
        "characters_involved": ["jinwoo"],
        "entities_involved": [],
        "tier": "structural",
        "temporal_status": "currently_true",
    },
]
