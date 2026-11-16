import os
import re
import shutil
import stat
import subprocess
from pathlib import Path

from app.config import settings

URL_RE = re.compile(
    r"^https://(?:github\.com|gitlab\.com|bitbucket\.org)/([\w.-]+)/([\w.-]+?)(?:\.git)?/?$"
)

SKIP_DIRS = {
    ".git", "node_modules", "venv", ".venv", "env", "__pycache__", "dist", "build",
    ".idea", ".vscode", ".next", "target", "vendor", ".mypy_cache", ".pytest_cache",
}

LANGUAGES = {
    ".py": "Python", ".js": "JavaScript", ".jsx": "JavaScript", ".ts": "TypeScript",
    ".tsx": "TypeScript", ".java": "Java", ".go": "Go", ".rs": "Rust", ".rb": "Ruby",
    ".php": "PHP", ".c": "C", ".h": "C", ".cpp": "C++", ".hpp": "C++", ".cs": "C#",
    ".kt": "Kotlin", ".swift": "Swift", ".html": "HTML", ".css": "CSS", ".scss": "CSS",
    ".sql": "SQL", ".sh": "Shell", ".md": "Markdown", ".json": "JSON", ".yml": "YAML",
    ".yaml": "YAML", ".toml": "TOML", ".txt": "Text", ".ipynb": "Notebook",
}


class RepoError(Exception):
    pass


def parse_repo_url(url: str) -> tuple[str, str]:
    """Validate the URL and return (clean_url, repo_name)."""
    match = URL_RE.match(url.strip())
    if not match:
        raise RepoError("Only public https GitHub, GitLab or Bitbucket repository URLs are supported")
    return url.strip().rstrip("/"), match.group(2)


def repo_path(user_id: str, name: str) -> Path:
    return Path(settings.repos_dir) / user_id / name


def _on_rm_error(func, path, _exc):
    os.chmod(path, stat.S_IWRITE)  # Windows marks .git files read-only
    func(path)


def clone_repo(url: str, dest: Path) -> None:
    if dest.exists():
        shutil.rmtree(dest, onerror=_on_rm_error)
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        subprocess.run(
            ["git", "clone", "--depth", "1", "--", url, str(dest)],
            check=True, capture_output=True, text=True, timeout=180,
            env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
        )
    except subprocess.CalledProcessError as exc:
        raise RepoError(f"git clone failed: {exc.stderr.strip()[-300:]}")
    except subprocess.TimeoutExpired:
        raise RepoError("git clone timed out")
    except FileNotFoundError:
        raise RepoError("git is not installed on the server")


def chunk_text(text: str, size: int, overlap: int) -> list[tuple[int, int, str]]:
    """Split text into overlapping line windows -> (start_line, end_line, content)."""
    lines = text.splitlines()
    step = max(size - overlap, 1)
    chunks = []
    for start in range(0, len(lines), step):
        part = lines[start:start + size]
        if "".join(part).strip():
            chunks.append((start + 1, start + len(part), "\n".join(part)))
        if start + size >= len(lines):
            break
    return chunks


def scan_repo(root: Path) -> tuple[list[dict], list[dict]]:
    """Walk the repo, returning (file_infos, chunk_docs without user/repo fields)."""
    files, chunks = [], []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
        for filename in sorted(filenames):
            full = Path(dirpath) / filename
            language = LANGUAGES.get(full.suffix.lower())
            if not language or full.is_symlink():
                continue
            if full.stat().st_size > settings.max_file_bytes:
                continue
            try:
                text = full.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue  # binary or unreadable
            rel = full.relative_to(root).as_posix()
            file_chunks = chunk_text(text, settings.chunk_lines, settings.chunk_overlap)
            files.append({
                "path": rel, "language": language,
                "size": len(text.encode()), "lines": len(text.splitlines()),
                "chunks": len(file_chunks),
            })
            for start, end, content in file_chunks:
                chunks.append({
                    # NOT "language": MongoDB text indexes treat that field name
                    # as a language override and reject values like "Python".
                    "file_path": rel, "lang": language,
                    "start_line": start, "end_line": end, "content": content,
                })
            if len(files) >= settings.max_files:
                return files, chunks
    return files, chunks


def read_repo_file(root: Path, rel: str) -> str:
    """Read one file, refusing anything outside the repo root (path traversal)."""
    target = (root / rel).resolve()
    if not target.is_relative_to(root.resolve()) or not target.is_file():
        raise FileNotFoundError(rel)
    return target.read_text(encoding="utf-8", errors="replace")
