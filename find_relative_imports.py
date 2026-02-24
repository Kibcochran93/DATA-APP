import os
import ast
from pathlib import Path

def find_relative_imports_in_file(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        try:
            tree = ast.parse(f.read(), filename=file_path)
        except SyntaxError as e:
            return [(file_path, -1, f"SyntaxError: {e}")]
    
    relative_imports = []

    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.level > 0:
                rel_path = "." * node.level + (node.module or "")
                relative_imports.append((file_path, node.lineno, rel_path))

    return relative_imports

def scan_directory_for_relative_imports(base_dir):
    results = []
    for dirpath, _, filenames in os.walk(base_dir):
        for filename in filenames:
            if filename.endswith(".py"):
                full_path = os.path.join(dirpath, filename)
                results.extend(find_relative_imports_in_file(full_path))
    return results

if __name__ == "__main__":
    project_root = Path(__file__).parent
    print(f"🔍 Scanning {project_root} for relative imports...\n")

    results = scan_directory_for_relative_imports(project_root)

    if results:
        for path, lineno, rel in results:
            print(f"📍 {path}:{lineno} → relative import: '{rel}'")
    else:
        print("✅ No relative imports found.")
