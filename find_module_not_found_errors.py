import os
import ast
import importlib
from pathlib import Path

def extract_imports(file_path):
    """Parse a file and extract all module names being imported."""
    with open(file_path, "r", encoding="utf-8") as f:
        try:
            tree = ast.parse(f.read(), filename=file_path)
        except SyntaxError:
            return []

    modules = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                modules.add(alias.name.split('.')[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                modules.add(node.module.split('.')[0])

    return list(modules)

def find_missing_modules(base_dir):
    seen_modules = set()
    missing_modules = {}

    for dirpath, _, filenames in os.walk(base_dir):
        for filename in filenames:
            if filename.endswith(".py"):
                file_path = os.path.join(dirpath, filename)
                imports = extract_imports(file_path)
                for mod in imports:
                    if mod in seen_modules:
                        continue
                    try:
                        importlib.import_module(mod)
                        seen_modules.add(mod)
                    except ModuleNotFoundError:
                        missing_modules.setdefault(mod, []).append(file_path)

    return missing_modules

if __name__ == "__main__":
    project_root = Path(__file__).parent
    print(f"🔍 Scanning {project_root} for modules that raise ModuleNotFoundError...\n")

    missing = find_missing_modules(project_root)

    if missing:
        for mod, files in missing.items():
            print(f"❌ ModuleNotFoundError: '{mod}' in:")
            for f in files:
                print(f"   - {f}")
    else:
        print("✅ No missing modules found.")
