"""Shared filesystem paths used across the pipeline's scraping and cleaning scripts."""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

DATA_DIR = PROJECT_ROOT / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
PROCESSED_DATA_DIR = DATA_DIR / "processed"


def ensure_dir(path: Path) -> Path:
    """Create `path` (and parents) if missing, and return it."""
    path.mkdir(parents=True, exist_ok=True)
    return path


def latest_file(directory: Path, pattern: str = "*.csv") -> Path:
    """Return the most recently modified file in `directory` matching `pattern`."""
    matches = [p for p in directory.glob(pattern) if p.is_file()]
    if not matches:
        raise FileNotFoundError(f"No files matching '{pattern}' found in {directory}")
    return max(matches, key=lambda p: p.stat().st_mtime)
