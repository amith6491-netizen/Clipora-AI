from datetime import datetime, timezone
from typing import Any

from pymongo import AsyncMongoClient, DESCENDING, ASCENDING

from app.core.config import Settings


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class DatabaseManager:
    """Async MongoDB wrapper and collection accessors."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.client: AsyncMongoClient | None = None
        self.db = None

    async def connect(self) -> None:
        if self.client is not None:
            return
        self.client = AsyncMongoClient(
            self.settings.mongodb_uri,
            serverSelectionTimeoutMS=5000,
        )
        self.db = self.client[self.settings.mongodb_db]
        await self.ensure_indexes()

    async def close(self) -> None:
        if self.client is not None:
            await self.client.close()
            self.client = None
            self.db = None

    async def ping(self) -> bool:
        try:
            if self.client is None:
                await self.connect()
            assert self.client is not None
            await self.client.admin.command("ping")
            return True
        except Exception:
            return False

    async def ensure_indexes(self) -> None:
        assert self.db is not None
        try:
            await self.users.create_index([("email", ASCENDING)], unique=True)
            await self.videos.create_index([("created_at", DESCENDING)])
            await self.videos.create_index([("user_id", ASCENDING), ("created_at", DESCENDING)])
            await self.clips.create_index([("video_id", ASCENDING), ("index", ASCENDING)])
            await self.clips.create_index([("video_id", ASCENDING), ("engagement_score", DESCENDING)])
            await self.analysis_artifacts.create_index([("video_id", ASCENDING)], unique=True)
            await self.exports.create_index([("video_id", ASCENDING), ("created_at", DESCENDING)])
        except Exception:
            # Startup should remain resilient even if MongoDB starts slightly after the API
            pass

    @property
    def users(self):
        assert self.db is not None
        return self.db["users"]

    @property
    def videos(self):
        assert self.db is not None
        return self.db["videos"]

    @property
    def clips(self):
        assert self.db is not None
        return self.db["clips"]

    @property
    def analysis_artifacts(self):
        assert self.db is not None
        return self.db["analysis_artifacts"]

    @property
    def exports(self):
        assert self.db is not None
        return self.db["exports"]

    async def create_user(self, doc: dict[str, Any]) -> None:
        await self.users.insert_one(doc)

    async def get_user_by_email(self, email: str) -> dict[str, Any] | None:
        return await self.users.find_one({"email": email.strip().lower()})

    async def get_user_by_id(self, user_id: str) -> dict[str, Any] | None:
        return await self.users.find_one({"_id": user_id})

    async def insert_video(self, doc: dict[str, Any]) -> None:
        await self.videos.insert_one(doc)

    async def get_video(self, video_id: str) -> dict[str, Any] | None:
        return await self.videos.find_one({"_id": video_id})

    async def list_videos(self, limit: int = 50, user_id: str | None = None) -> list[dict[str, Any]]:
        query = {"user_id": user_id} if user_id else {}
        cursor = self.videos.find(query).sort("created_at", DESCENDING).limit(limit)
        return await cursor.to_list(length=limit)

    async def update_video(self, video_id: str, fields: dict[str, Any]) -> None:
        fields["updated_at"] = utc_now()
        await self.videos.update_one({"_id": video_id}, {"$set": fields})

    async def delete_video(self, video_id: str) -> None:
        await self.videos.delete_one({"_id": video_id})
        await self.clips.delete_many({"video_id": video_id})
        await self.analysis_artifacts.delete_many({"video_id": video_id})
        await self.exports.delete_many({"video_id": video_id})

    async def save_analysis_artifacts(self, video_id: str, payload: dict[str, Any]) -> None:
        await self.analysis_artifacts.update_one(
            {"video_id": video_id},
            {"$set": {"video_id": video_id, **payload, "updated_at": utc_now()}},
            upsert=True,
        )

    async def get_analysis_artifacts(self, video_id: str) -> dict[str, Any] | None:
        return await self.analysis_artifacts.find_one({"video_id": video_id})

    async def replace_clips_for_video(self, video_id: str, clip_docs: list[dict[str, Any]]) -> None:
        await self.clips.delete_many({"video_id": video_id})
        if clip_docs:
            await self.clips.insert_many(clip_docs)

    async def list_clips(self, video_id: str) -> list[dict[str, Any]]:
        cursor = self.clips.find({"video_id": video_id}).sort("index", ASCENDING)
        return await cursor.to_list(length=100)

    async def get_clip(self, clip_id: str) -> dict[str, Any] | None:
        return await self.clips.find_one({"_id": clip_id})

    async def update_clip(self, clip_id: str, fields: dict[str, Any]) -> dict[str, Any] | None:
        fields["updated_at"] = utc_now()
        await self.clips.update_one({"_id": clip_id}, {"$set": fields})
        return await self.get_clip(clip_id)

    async def insert_export(self, doc: dict[str, Any]) -> None:
        await self.exports.insert_one(doc)

    async def list_exports(
        self,
        video_id: str | None = None,
        limit: int = 50,
        user_id: str | None = None,
    ) -> list[dict[str, Any]]:
        query: dict[str, Any] = {}
        if video_id:
            query["video_id"] = video_id
        if user_id:
            query["user_id"] = user_id
        cursor = self.exports.find(query).sort("created_at", DESCENDING).limit(limit)
        return await cursor.to_list(length=limit)

    async def get_export(self, export_id: str) -> dict[str, Any] | None:
        return await self.exports.find_one({"_id": export_id})
