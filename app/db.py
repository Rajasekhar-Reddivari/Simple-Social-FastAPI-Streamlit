from collections.abc import AsyncGenerator
import uuid
from sqlalchemy import Column,String , Text ,DateTime , ForeignKey, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.asyncio import AsyncSession,create_async_engine , async_sessionmaker
from sqlalchemy.orm import DeclarativeBase ,relationship
from datetime import datetime
from fastapi_users.db import SQLAlchemyUserDatabase, SQLAlchemyBaseUserTableUUID
from fastapi import Depends

DATABASE_URL = "sqlite+aiosqlite:///./test.db"

class Base(DeclarativeBase):
    pass

class User(SQLAlchemyBaseUserTableUUID, Base):
    posts = relationship("Post", back_populates="user")

class Post(Base):
    __tablename__ = "posts"

    id = Column(UUID(as_uuid=True),primary_key=True,default=uuid.uuid4)
    # make user_id nullable so we can add it to existing DBs without failing
    user_id = Column(UUID(as_uuid=True), ForeignKey("user.id"), nullable=True)
    caption = Column(Text)
    url = Column(String , unique=False)
    file_type = Column(String , nullable=False)
    file_name = Column(String , nullable=False)
    file_id = Column(String, nullable=True)  # ImageKit file id (nullable for older rows)
    created_at = Column(DateTime ,default=datetime.utcnow)
    user = relationship("User", back_populates="posts")

engine = create_async_engine(DATABASE_URL)
async_session_maker = async_sessionmaker(engine,expire_on_commit=False)

async def create_db_and_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # For existing SQLite DBs, create_all won't add columns to an existing table.
        # If using the default sqlite DB in development, ensure `file_id` and `user_id` columns exist.
        if DATABASE_URL.startswith("sqlite"):
            # Check existing columns in posts
            result = await conn.execute(text("PRAGMA table_info('posts')"))
            cols = [row[1] for row in result.fetchall()]
            if 'file_id' not in cols:
                # Add the nullable text column
                await conn.execute(text("ALTER TABLE posts ADD COLUMN file_id TEXT;"))
            if 'user_id' not in cols:
                # Add the nullable user_id column (store UUID as text)
                await conn.execute(text("ALTER TABLE posts ADD COLUMN user_id TEXT;"))


async def get_async_session() -> AsyncGenerator[AsyncSession,None]:
    async with async_session_maker() as session:
        yield session

async def get_user_db(session: AsyncSession = Depends(get_async_session)):
    yield SQLAlchemyUserDatabase(session, User)