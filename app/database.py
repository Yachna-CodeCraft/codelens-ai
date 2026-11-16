from motor.motor_asyncio import AsyncIOMotorClient

from app.config import settings

client = AsyncIOMotorClient(settings.mongo_uri)
db = client[settings.mongo_db]


async def init_indexes() -> None:
    await db.users.create_index("email", unique=True)
    await db.repos.create_index([("user_id", 1), ("name", 1)], unique=True)
    await db.chunks.create_index([("user_id", 1), ("repo_name", 1)])
    # Full-text index used by the assistant to retrieve relevant code.
    await db.chunks.create_index([("content", "text"), ("file_path", "text")])
