from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    discord_id = Column(String(100), unique=True)
    personality_traits = Column(Text)  # JSON形式で保存
    interaction_history = relationship("Interaction", back_populates="user")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Interaction(Base):
    __tablename__ = 'interactions'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    message_content = Column(Text)
    importance_score = Column(Float)  # メッセージの重要度スコア
    character_id = Column(String(100))  # 対話したキャラクターのID
    created_at = Column(DateTime, default=datetime.utcnow)
    
    user = relationship("User", back_populates="interaction_history")

class Character(Base):
    __tablename__ = 'characters'
    
    id = Column(Integer, primary_key=True)
    character_id = Column(String(100), unique=True)
    name = Column(String(100))
    personality = Column(Text)
    avatar_url = Column(String(255))
    voice_id = Column(Integer)
    is_active = Column(Integer, default=0)  # 0: inactive, 1: active
    last_active = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow) 