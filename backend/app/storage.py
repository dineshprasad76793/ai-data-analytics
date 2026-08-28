from pathlib import Path
import uuid, time
from .config import UPLOAD_TTL_SECONDS

BASE = Path(__file__).resolve().parent.parent / "storage"
BASE.mkdir(parents=True, exist_ok=True)

def new_id(): return uuid.uuid4().hex

def path_for(dataset_id: str) -> Path: return BASE / f"{dataset_id}.bin"

def meta_path(dataset_id: str) -> Path: return BASE / f"{dataset_id}.json"

def cleanup_old():
    now = time.time()
    for p in BASE.glob("*.json"):
        try:
            if now - p.stat().st_mtime > UPLOAD_TTL_SECONDS:
                did = p.stem
                p.unlink(missing_ok=True)
                path_for(did).unlink(missing_ok=True)
        except OSError: pass
