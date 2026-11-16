from collections import Counter
from pathlib import Path

from app.services import ai_service
from app.services.repo_service import read_repo_file

ENTRY_POINTS = {
    "main.py", "app.py", "manage.py", "server.py", "index.js", "server.js",
    "app.js", "index.ts", "main.go", "main.rs", "Main.java",
}
DEPENDENCY_FILES = {
    "requirements.txt", "pyproject.toml", "package.json", "go.mod", "Cargo.toml",
    "pom.xml", "build.gradle", "Gemfile", "composer.json",
}


def build_statistics(files: list[dict]) -> dict:
    by_lang = Counter()
    for f in files:
        by_lang[f["language"]] += f["lines"]
    top_dirs = Counter(f["path"].split("/")[0] for f in files if "/" in f["path"])
    names = {Path(f["path"]).name: f["path"] for f in files}
    return {
        "languages": dict(by_lang.most_common()),
        "top_level_directories": dict(top_dirs.most_common(10)),
        "entry_points": [p for n, p in names.items() if n in ENTRY_POINTS],
        "dependency_files": [p for n, p in names.items() if n in DEPENDENCY_FILES],
        "total_lines": sum(f["lines"] for f in files),
    }


def readme_excerpt(root: Path, files: list[dict], limit: int = 3000) -> str:
    for f in files:
        if Path(f["path"]).name.lower().startswith("readme"):
            try:
                return read_repo_file(root, f["path"])[:limit]
            except FileNotFoundError:
                break
    return ""


async def generate_summary(repo: dict, root: Path) -> dict:
    stats = build_statistics(repo["files"])
    readme = readme_excerpt(root, repo["files"])
    summary = {"statistics": stats, "readme_excerpt": readme[:600], "ai_summary": None}

    if ai_service.ai_enabled():
        prompt = (
            f"Repository: {repo['name']}\n"
            f"Languages (lines): {stats['languages']}\n"
            f"Top-level directories: {stats['top_level_directories']}\n"
            f"Entry points: {stats['entry_points']}\n"
            f"Dependency files: {stats['dependency_files']}\n\n"
            f"README:\n{readme or '(none)'}\n\n"
            "Write a concise project summary: what it does, how it is structured, "
            "the tech stack, and where a new developer should start reading."
        )
        summary["ai_summary"] = await ai_service.complete(
            "You summarize software repositories for new contributors.", prompt, max_tokens=700
        )
    return summary
