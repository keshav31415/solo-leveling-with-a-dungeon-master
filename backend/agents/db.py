import os
from sqlalchemy import create_engine, Column, String, DateTime, JSON
from sqlalchemy.orm import DeclarativeBase, Session
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "../.env"), override=True)

_DATABASE_URL = os.getenv("DATABASE_URL")
if not _DATABASE_URL:
    raise RuntimeError("DATABASE_URL not set in .env")

engine = create_engine(_DATABASE_URL, pool_pre_ping=True)


class Base(DeclarativeBase):
    pass


class RuntimeMemoryRow(Base):
    __tablename__ = "runtime_memory"

    scene_id          = Column(String, primary_key=True)
    world_state       = Column(JSON, default=dict)
    relationships     = Column(JSON, default=dict)
    knowledge         = Column(JSON, default=list)
    events_fired      = Column(JSON, default=list)
    candidates        = Column(JSON, default=list)
    current_situation = Column(String, default="")
    updated_at        = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class SceneChronicleRow(Base):
    __tablename__ = "scene_chronicles"

    id                   = Column(String, primary_key=True)  # scene_id + timestamp
    scene_id             = Column(String, nullable=False)
    summary              = Column(String, default="")
    major_events         = Column(JSON, default=list)
    relationship_changes = Column(JSON, default=list)
    knowledge_gained     = Column(JSON, default=list)
    character_deaths     = Column(JSON, default=list)
    mysteries_revealed   = Column(JSON, default=list)
    created_at           = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class StoryCanonRow(Base):
    __tablename__ = "story_canon"

    id           = Column(String, primary_key=True)  # uuid
    fact         = Column(String, nullable=False)
    category     = Column(String, nullable=False)
    scene_origin = Column(String, default="")
    created_at   = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class NPCMemoryRow(Base):
    __tablename__ = "npc_memory"

    id                 = Column(String, primary_key=True)  # f"{npc_id}__{scene_id}"
    npc_id             = Column(String, nullable=False)
    scene_id           = Column(String, nullable=False)
    key_exchanges      = Column(JSON, default=list)   # 3-5 significant dialogue moments
    relationship_delta = Column(JSON, default=dict)   # {trust: +12, fear: -5, respect: +3}
    shared_events      = Column(JSON, default=list)   # director event IDs witnessed
    emotional_state    = Column(String, default="")   # how NPC ended the scene
    created_at         = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class ScenePlanRow(Base):
    __tablename__ = "scene_plans"

    scene_id   = Column(String, primary_key=True)
    events     = Column(JSON, default=list)  # list of PlannedEvent dicts
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


def init_db():
    Base.metadata.create_all(engine)


def get_session() -> Session:
    return Session(engine)
