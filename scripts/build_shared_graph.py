"""Rebuild the exported graph without a Codex installation or network access."""
from html import escape
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
MARKER = "<!--__ESCAPED_ONTOLOGY_FRAGMENT__-->"


def main():
    fragment_path = ROOT / "docs/ontology-explorer.fragment.html"
    subprocess.run(
        [sys.executable, str(ROOT / "ontology-prototype/discovery-platform/build_visualization.py"), str(fragment_path)],
        check=True,
    )
    fragment = fragment_path.read_text(encoding="utf-8")
    template = (ROOT / "scripts/standalone.template.html").read_text(encoding="utf-8")
    if template.count(MARKER) != 1:
        raise ValueError("Standalone template must contain exactly one fragment marker")
    if "window.openai" in fragment or "globalThis.openai" in fragment:
        raise ValueError("Shared graph must not depend on a Codex host API")
    document = template.replace(MARKER, escape(fragment))
    output = ROOT / "docs/ontology-explorer.html"
    output.write_text(document, encoding="utf-8", newline="\n")
    print(f"Shared graph: {output.relative_to(ROOT)} ({len(document.encode('utf-8'))} bytes)")


if __name__ == "__main__":
    main()
