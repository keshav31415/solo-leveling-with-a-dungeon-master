SCENE_CONFIGS = {
    "double_dungeon": {
        "arc":        "double_dungeon",
        "characters": ["joohee", "song_chiyul", "mr_park", "mr_kim"],
        "entities":   ["giant_statue", "stone_tablet", "entrance_door"],
    },
}


def get_scene_config(scene_id: str) -> dict:
    return SCENE_CONFIGS.get(scene_id, {
        "arc":        scene_id,
        "characters": [],
        "entities":   [],
    })
