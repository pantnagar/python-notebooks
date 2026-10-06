"""Create a readable inventory of the repository's folders and files."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "folder_log.txt"
EXCLUDED_DIRECTORIES = {".git"}
EXCLUDED_FILES = {".git", OUTPUT.name}


def iter_folders() -> list[Path]:
    """Return project folders in stable relative-path order."""
    folders = [
        path
        for path in ROOT.rglob("*")
        if path.is_dir()
        and not any(part in EXCLUDED_DIRECTORIES for part in path.relative_to(ROOT).parts)
    ]
    return sorted(folders, key=lambda path: path.relative_to(ROOT).as_posix().lower())


def format_folder(folder: Path) -> list[str]:
    relative_folder = (
        "."
        if folder == ROOT
        else folder.relative_to(ROOT).as_posix()
    )
    files = sorted(
        (
            path
            for path in folder.iterdir()
            if path.is_file() and path.name not in EXCLUDED_FILES
        ),
        key=lambda path: path.name.lower(),
    )
    lines = [f"[{relative_folder}] ({len(files)} file(s))"]
    lines.extend(f"  - {file.name}" for file in files)
    if not files:
        lines.append("  - (no files)")
    return lines


def build_log() -> str:
    folders = [ROOT, *iter_folders()]
    lines = [
        "Folder inventory",
        f"Generated: {datetime.now().astimezone().isoformat(timespec='seconds')}",
        f"Root: {ROOT}",
        "",
    ]
    for index, folder in enumerate(folders):
        if index:
            lines.append("")
        lines.extend(format_folder(folder))
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    OUTPUT.write_text(build_log(), encoding="utf-8")
    print(f"Wrote {OUTPUT}")
