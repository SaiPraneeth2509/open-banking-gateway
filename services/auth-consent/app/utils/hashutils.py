from __future__ import annotations
import hashlib, json
from typing import Any, Dict

def canonical_sha256(data: Dict[str, Any]) -> str:
    # Stable JSON -> SHA256 so the same logical payload always hashes the same
    s = json.dumps(data, sort_keys=True, separators=(",", ":"), default=str, ensure_ascii=False)
    return hashlib.sha256(s.encode("utf-8")).hexdigest()
