"""
Persisted header-mapping memory.

During onboarding you import from the *same* institution's SIS repeatedly, with
the same source headings each time. This remembers the SEAtS-field -> source-
column mapping keyed by a signature of (dataset type + the set of source
headings), so a repeat upload auto-applies the previous mapping instead of
re-mapping by hand. Ported from the v2.1 browser tool's localStorage memory
(mappingSignature / getSavedMappings / saveMapping / buildMapping).

Storage is a JSON file (default: data/runtime/header_mappings.json), so it
persists across runs of the Streamlit app on the same machine.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, List, Optional

_DEFAULT_PATH = Path(__file__).resolve().parent.parent / "data" / "runtime" / "header_mappings.json"

_NORM_RE = re.compile(r"[^a-z0-9]")


def _norm(value: str) -> str:
    return _NORM_RE.sub("", str(value).lower())


def mapping_signature(dataset_type: str, source_headings: List[str]) -> str:
    """Stable key for a (dataset type, set-of-source-headings) pair."""
    normalized = sorted(_norm(h) for h in source_headings if str(h).strip())
    return f"{dataset_type}::" + "|".join(normalized)


def _store_path(path: Optional[Path]) -> Path:
    return Path(path) if path is not None else _DEFAULT_PATH


def load_all(path: Optional[Path] = None) -> Dict[str, Dict[str, str]]:
    store = _store_path(path)
    try:
        return json.loads(store.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}


def get_saved_mapping(signature: str, path: Optional[Path] = None) -> Optional[Dict[str, str]]:
    return load_all(path).get(signature)


def save_mapping(signature: str, mapping: Dict[str, str], path: Optional[Path] = None) -> None:
    """Persist a mapping under its signature (empty values are kept as "don't map")."""
    store = _store_path(path)
    data = load_all(path)
    data[signature] = {str(k): ("" if v is None else str(v)) for k, v in mapping.items()}
    store.parent.mkdir(parents=True, exist_ok=True)
    store.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")


def remembered_mapping(
    dataset_type: str,
    source_headings: List[str],
    target_fields: List[str],
    path: Optional[Path] = None,
) -> Dict[str, str]:
    """Return the saved mapping for this signature, re-resolved against the
    current source headings.

    Each SEAtS ``target_field`` maps to whichever current source heading matches
    (case/format-insensitively) the remembered choice; unmatched targets map to
    "" (do not map). Returns an empty dict when nothing is remembered.
    """
    saved = get_saved_mapping(mapping_signature(dataset_type, source_headings), path)
    if not saved:
        return {}
    by_norm = {_norm(h): h for h in source_headings}
    resolved: Dict[str, str] = {}
    for target in target_fields:
        wanted = saved.get(target, "")
        resolved[target] = by_norm.get(_norm(wanted), "") if wanted else ""
    return resolved
