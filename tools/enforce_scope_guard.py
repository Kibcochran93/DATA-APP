import json
import os
import sys
from pathlib import Path

# Load scope definition
try:
    with open("FEATURE_SCOPE.json", "r") as f:
        scope = json.load(f)
except FileNotFoundError:
    print("❌ FEATURE_SCOPE.json not found.")
    sys.exit(1)

# Flatten allowed modules into full relative paths
allowed_paths = set()
for group, paths in scope["modules_allowed"].items():
    for path in paths:
        if "**" in path:
            matched = list(Path(".").rglob(path.replace("**", "*")))
            allowed_paths.update(str(p.resolve().relative_to(Path.cwd())).replace("\\", "/") for p in matched)
        else:
            allowed_paths.add(path.replace("\\", "/"))

# Check current project files
violations = []
for path in Path(".").rglob("*"):
    if path.is_file():
        rel_path = str(path.resolve().relative_to(Path.cwd())).replace("\\", "/")
        if rel_path not in allowed_paths and not rel_path.startswith((".git", ".cursor", "__pycache__")):
            violations.append(rel_path)

# Warn on unsupported datasets (based on folder names in data/master)
dataset_dir = Path("data/master")
declared_datasets = set([ds.lower() for ds in scope.get("datasets_supported", [])])
if dataset_dir.exists():
    for item in dataset_dir.iterdir():
        if item.is_dir() and item.name.lower() not in declared_datasets:
            violations.append(f"🚫 Unsupported dataset directory: data/master/{item.name}")

# Print results
if violations:
    print("🔒 Scope Guard Violations Found:")
    for v in violations:
        print("  -", v)
    sys.exit(1)
else:
    print("✅ All files and datasets are within the defined scope.")
    sys.exit(0)
