import os
import ast
import importlib.util
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent

def is_import_resolvable(module_name):
    try:
        spec = importlib.util.find_spec(module_name)
        return spec is not None
    except ModuleNotFoundError:
        return False

def scan_file_for_imports(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        tree = ast.parse(f.read(), filename=file_path)

    errors = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if not is_import_resolvable(alias.name):
                    errors.append((file_path, alias.name))
        elif isinstance(node, ast.ImportFrom):
            module = node.module
            if module and not is_import_resolvable(module):
                errors.append((file_path, module))
    return errors

def scan_project(root):
    all_errors = []
    for dirpath, _, filenames in os.walk(root):
        for filename in filenames:
            if filename.endswith(".py"):
                filepath = os.path.join(dirpath, filename)
                all_errors.extend(scan_file_for_imports(filepath))
    return all_errors

if __name__ == "__main__":
    print(f"🔍 Scanning {PROJECT_ROOT} for unresolved imports...\n")
    errors = scan_project(PROJECT_ROOT)
    if errors:
        for file_path, import_name in errors:
            print(f"❌ Unresolved import: '{import_name}' in {file_path}")
    else:
        print("✅ No unresolved imports found.")
