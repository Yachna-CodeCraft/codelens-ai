from fastapi import APIRouter, Depends, HTTPException

from app.database import db
from app.schemas import AskRequest
from app.security import get_current_user
from app.services import ai_service

router = APIRouter(prefix="/assistant", tags=["Assistant"])


@router.post("/ask")
async def ask(body: AskRequest, user: dict = Depends(get_current_user)):
    user_id = str(user["_id"])
    if not await db.repos.find_one({"user_id": user_id, "name": body.repo_name}, {"_id": 1}):
        raise HTTPException(404, "Repository not analyzed yet")

    scope = {"user_id": user_id, "repo_name": body.repo_name}
    cursor = (
        db.chunks.find(
            {**scope, "$text": {"$search": body.question}},
            {"score": {"$meta": "textScore"}},
        )
        .sort([("score", {"$meta": "textScore"})])
        .limit(6)
    )
    chunks = await cursor.to_list(6)
    if not chunks:  # e.g. question made only of stop-words
        chunks = await db.chunks.find(scope).limit(4).to_list(4)

    answer = await ai_service.answer_question(body.question, chunks)
    return {
        "answer": answer,
        "sources": [
            {
                "file_path": c["file_path"],
                "start_line": c["start_line"],
                "end_line": c["end_line"],
                "snippet": c["content"][:400],
            }
            for c in chunks
        ],
    }
