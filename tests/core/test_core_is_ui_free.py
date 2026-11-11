"""Architecture rule: the PDF logic (app.core) never depends on the interface."""

import ast
import subprocess
import sys
from pathlib import Path

CORE_DIR = Path(__file__).resolve().parents[2] / "app" / "core"
FORBIDDEN = ("PySide6", "shiboken6", "app.ui")


def imported_modules(source: str) -> set[str]:
    modules: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
            modules.update(f"{node.module}.{alias.name}" for alias in node.names)
    return modules


def test_core_does_not_import_the_interface():
    offenders = []
    for file in sorted(CORE_DIR.rglob("*.py")):
        for module in imported_modules(file.read_text(encoding="utf-8")):
            if any(module == bad or module.startswith(bad + ".") for bad in FORBIDDEN):
                offenders.append(f"{file.relative_to(CORE_DIR)} imports {module}")
    assert not offenders, "app.core must not depend on the interface: " + "; ".join(offenders)


def test_core_has_files_to_check():
    assert list(CORE_DIR.rglob("*.py"))


def test_pdf_engine_does_not_load_machine_learning_parts():
    # PyMuPDF 2 installs machine-learning layout tools next to the PDF engine.
    # The program must never load them: they are left out of the Windows build.
    code = (
        "import sys; import app.core.document; "
        "bad = [m for m in ('numpy', 'onnxruntime', 'pymupdf4llm', 'pymupdf.layout') "
        "if m in sys.modules]; "
        "sys.exit(', '.join(bad) or 0)"
    )
    result = subprocess.run(
        [sys.executable, "-c", code], cwd=CORE_DIR.parents[1], capture_output=True, text=True
    )
    assert result.returncode == 0, f"Loaded at start: {result.stderr.strip()}"
