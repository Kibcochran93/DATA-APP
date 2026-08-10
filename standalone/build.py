#!/usr/bin/env python3
"""
Build the standalone SEATS Validator HTML.

Generates the embedded data (specs + column mappings) from the SAME source JSONs
the Python engine uses, then assembles one self-contained .html by inlining:
  - SheetJS (extracted from the existing v2.1 tool, so we don't re-embed a blob)
  - the generated data (window.SEATS_DATA)
  - the pure-JS engine (standalone/engine.js)
into standalone/template.html (which holds the UI + glue).

Usage:  python standalone/build.py [path-to-v2.1.html]
Outputs: standalone/seats_data.json  and  standalone/seats_validator.html
"""
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
MASTER = REPO / "data" / "master"
MAPPINGS = REPO / "data" / "mappings"

SPEC_FILES = {
    "Student": "student_data_spec.json",
    "Staff": "staff_data_spec.json",
    "StudentTimetable": "student_timetable_spec.json",
}

ENUM_EXPANSIONS = {
    "GENDER": {"MALE": "M", "FEMALE": "F", "OTHER": "O", "M": "M", "F": "F", "O": "O",
               "MAN": "M", "WOMAN": "F", "NONBINARY": "O", "NON-BINARY": "O"},
    "VISAREQUIRED": {"YES": "Y", "NO": "N", "TRUE": "Y", "FALSE": "N", "Y": "Y", "N": "N"},
}


def build_spec(path: Path) -> dict:
    spec = json.loads(path.read_text(encoding="utf-8"))
    fields_spec = spec.get("fields", {})
    ordered = sorted(fields_spec, key=lambda k: fields_spec[k].get("position", 9999))
    enums = {f: fields_spec[f]["values"] for f in ordered
             if fields_spec[f].get("type") == "enum" and fields_spec[f].get("values")}
    dates = [f for f in ordered if fields_spec[f].get("type") == "date"]
    return {
        "datasetType": spec.get("dataset_type"),
        "version": spec.get("version"),
        "fields": ordered,
        "mandatory": spec.get("mandatory_fields", []),
        "enums": enums,
        "dates": dates,
    }


def build_data() -> dict:
    specs = {name: build_spec(MASTER / fn) for name, fn in SPEC_FILES.items()}
    column_mappings = []
    for fn in ("sis_to_seats_mapping.json", "lms_to_seats_mapping.json"):
        p = MAPPINGS / fn
        if p.exists():
            column_mappings.append(json.loads(p.read_text(encoding="utf-8")).get("column_mappings", {}))
    return {"specs": specs, "columnMappings": column_mappings, "enumExpansions": ENUM_EXPANSIONS}


def extract_sheetjs(v21_path: Path) -> str:
    """Return the first <script>...</script> block that contains SheetJS."""
    html = v21_path.read_text(encoding="utf-8", errors="replace")
    for m in re.finditer(r"<script\b[^>]*>.*?</script>", html, re.DOTALL | re.IGNORECASE):
        if "SheetJS" in m.group(0) or "xlsx.js" in m.group(0):
            return m.group(0)
    raise SystemExit("Could not find the SheetJS <script> block in " + str(v21_path))


def main():
    v21 = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(
        r"C:/Users/KibCochran/Downloads/SEAtS_Data_Validator_v2_1(1) 1.html")

    data = build_data()
    (HERE / "seats_data.json").write_text(json.dumps(data, indent=2), encoding="utf-8")
    print("wrote seats_data.json  (specs:", ", ".join(f"{k}={len(v['fields'])}f/{len(v['mandatory'])}m"
          for k, v in data["specs"].items()), ")")

    template = (HERE / "template.html").read_text(encoding="utf-8")
    engine = (HERE / "engine.js").read_text(encoding="utf-8")
    sheetjs = extract_sheetjs(v21)
    data_script = "<script>window.SEATS_DATA = " + json.dumps(data) + ";</script>"
    engine_script = "<script>\n" + engine + "\n</script>"

    html = (template
            .replace("<!--INJECT_SHEETJS-->", sheetjs)
            .replace("<!--INJECT_DATA-->", data_script)
            .replace("<!--INJECT_ENGINE-->", engine_script))

    out = HERE / "seats_validator.html"
    out.write_text(html, encoding="utf-8")
    kb = out.stat().st_size / 1024
    print(f"wrote seats_validator.html  ({kb:.0f} KB, self-contained)")

    # Artifact-ready variant: no outer <!doctype>/<html>/<head>/<body> wrapper
    # (the hosting skeleton supplies those); keep the <style> + inner body + scripts.
    m_style = re.search(r"<style>.*?</style>", html, re.DOTALL | re.IGNORECASE)
    m_body = re.search(r"<body[^>]*>(.*?)</body>", html, re.DOTALL | re.IGNORECASE)
    artifact = (m_style.group(0) if m_style else "") + "\n" + (m_body.group(1) if m_body else html)
    (HERE / "seats_validator.artifact.html").write_text(artifact, encoding="utf-8")
    print("wrote seats_validator.artifact.html  (for publishing as a hosted link)")


if __name__ == "__main__":
    main()
