import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from fastapi.concurrency import run_in_threadpool

from app.database import db
from app.schemas import AnalyzeRequest
from app.security import get_current_user
from app.services import repo_service as rs
from app.services.summary_service import generate_summary

router = APIRouter(prefix="/repos", tags=["Repositories"])
log = logging.getLogger("codelens")


async def _get_repo(user: dict, name: str) -> dict:
    repo = await db.repos.find_one({"user_id": str(user["_id"]), "name": name})
    if not repo:
        raise HTTPException(404, "Repository not analyzed yet")
    return repo


@router.post("/analyze")
async def analyze(body: AnalyzeRequest, user: dict = Depends(get_current_user)):
    user_id = str(user["_id"])
    try:
        url, name = rs.parse_repo_url(body.repo_url)
        dest = rs.repo_path(user_id, name)
        await run_in_threadpool(rs.clone_repo, url, dest)
        files, chunks = await run_in_threadpool(rs.scan_repo, dest)
    except rs.RepoError as exc:
        raise HTTPException(400, str(exc))
    except Exception as exc:
        log.exception("clone/scan failed")
        raise HTTPException(500, f"Scan failed: {type(exc).__name__}: {exc}")

    if not files:
        raise HTTPException(422, "No supported source files found in this repository")

    try:
        # Replace any previous analysis of the same repo.
        await db.chunks.delete_many({"user_id": user_id, "repo_name": name})
        docs = [{**c, "user_id": user_id, "repo_name": name} for c in chunks]
        stored = len((await db.chunks.insert_many(docs)).inserted_ids) if docs else 0

        await db.repos.update_one(
            {"user_id": user_id, "name": name},
            {"$set": {
                "url": url, "path": dest.as_posix(), "files": files,
                "total_files": len(files), "total_chunks": len(chunks),
                "analyzed_at": datetime.now(timezone.utc), "summary": None,
            }},
            upsert=True,
        )
    except Exception as exc:
        log.exception("database write failed")
        raise HTTPException(500, f"Database error: {type(exc).__name__}: {exc}")
    return {
        "status": "success",
        "repo_name": name,
        "repository_path": dest.as_posix(),
        "total_files": len(files),
        "total_chunks": len(chunks),
        "stored_chunks": stored,
    }


@router.get("")
async def list_repos(user: dict = Depends(get_current_user)):
    cursor = db.repos.find(
        {"user_id": str(user["_id"])},
        {"_id": 0, "name": 1, "url": 1, "total_files": 1, "total_chunks": 1, "analyzed_at": 1},
    ).sort("analyzed_at", -1)
    return await cursor.to_list(100)


@router.get("/{name}/files")
async def list_files(name: str, user: dict = Depends(get_current_user)):
    repo = await _get_repo(user, name)
    return {"repo_name": name, "total_files": repo["total_files"], "files": repo["files"]}


@router.get("/{name}/files/{file_path:path}")
async def inspect_file(name: str, file_path: str, user: dict = Depends(get_current_user)):
    repo = await _get_repo(user, name)
    info = next((f for f in repo["files"] if f["path"] == file_path), None)
    if not info:
        raise HTTPException(404, "File not found in this repository")
    try:
        content = rs.read_repo_file(rs.repo_path(str(user["_id"]), name), file_path)
    except FileNotFoundError:
        raise HTTPException(404, "File is no longer on disk; re-run the analysis")
    return {**info, "content": content}


@router.get("/{name}/summary")
async def summary(name: str, refresh: bool = False, user: dict = Depends(get_current_user)):
    repo = await _get_repo(user, name)
    if repo.get("summary") and not refresh:
        return repo["summary"]
    result = await generate_summary(repo, rs.repo_path(str(user["_id"]), name))
    await db.repos.update_one({"_id": repo["_id"]}, {"$set": {"summary": result}})
    return result
