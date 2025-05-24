from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import Session
from contextlib import contextmanager
import json
from datetime import datetime
import logging
from typing import List, Optional

from .models import Base, User, Interaction, Character

logger = logging.getLogger(__name__)

class Database:
    def __init__(self, db_url: str = "sqlite+aiosqlite:///bot_database.db"):
        self.engine = create_async_engine(db_url, echo=True)
        self.SessionLocal = sessionmaker(
            bind=self.engine,
            class_=AsyncSession,
            expire_on_commit=False
        )

    async def init_db(self):
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def get_session(self) -> AsyncSession:
        async with self.SessionLocal() as session:
            return session

    async def get_or_create_user(self, session: AsyncSession, discord_id: str) -> User:
        user = await session.query(User).filter(User.discord_id == discord_id).first()
        if not user:
            user = User(discord_id=discord_id, personality_traits="{}")
            session.add(user)
            await session.commit()
        return user

    async def update_user_personality(self, session: AsyncSession, discord_id: str, traits: dict):
        user = await self.get_or_create_user(session, discord_id)
        user.personality_traits = json.dumps(traits)
        await session.commit()

    async def add_interaction(self, session: AsyncSession, discord_id: str, 
                            message: str, importance: float, character_id: str):
        user = await self.get_or_create_user(session, discord_id)
        interaction = Interaction(
            user_id=user.id,
            message_content=message,
            importance_score=importance,
            character_id=character_id
        )
        session.add(interaction)
        await session.commit()

    async def get_user_history(self, session: AsyncSession, discord_id: str, 
                              limit: int = 10) -> List[Interaction]:
        user = await self.get_or_create_user(session, discord_id)
        return await session.query(Interaction)\
            .filter(Interaction.user_id == user.id)\
            .order_by(Interaction.created_at.desc())\
            .limit(limit)\
            .all()

    async def update_character_status(self, session: AsyncSession, character_id: str, 
                                    is_active: bool):
        character = await session.query(Character)\
            .filter(Character.character_id == character_id)\
            .first()
        if character:
            character.is_active = 1 if is_active else 0
            character.last_active = datetime.utcnow() if is_active else character.last_active
            await session.commit()

    async def get_active_characters(self, session: AsyncSession) -> List[Character]:
        return await session.query(Character)\
            .filter(Character.is_active == 1)\
            .all()

    async def get_inactive_characters(self, session: AsyncSession) -> List[Character]:
        return await session.query(Character)\
            .filter(Character.is_active == 0)\
            .all()

    async def get_user_personality(self, session: AsyncSession, discord_id: str) -> dict:
        user = await self.get_or_create_user(session, discord_id)
        try:
            return json.loads(user.personality_traits) if user.personality_traits else {}
        except Exception:
            return {} 