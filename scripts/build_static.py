"""Validate and copy only public assets to dist for static hosting."""
import json
import shutil
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class DocumentCheck(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = set()

    def handle_starttag(self, tag, attrs):
        node_id = dict(attrs).get("id")
        if node_id:
            if node_id in self.ids:
                raise ValueError(f"Duplicate DOM id: {node_id}")
            self.ids.add(node_id)


def build():
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    DocumentCheck().feed(html)
    for p in (ROOT / "data").rglob("*.json"):
        json.loads(p.read_text(encoding="utf-8"), parse_constant=lambda v: (_ for _ in ()).throw(ValueError(v)))
    output = ROOT / "dist"
    # This generated directory is the only deletion target.
    if output.exists():
        if output.is_symlink() or output.resolve().parent != ROOT.resolve():
            raise ValueError("Unsafe output path")
        shutil.rmtree(output)
    output.mkdir()
    output = output / "client"
    output.mkdir()
    shutil.copy2(ROOT / "index.html", output / "index.html")
    shutil.copytree(ROOT / "data", output / "data")
    shutil.copy2(ROOT / ".nojekyll", output / ".nojekyll")
    print(f"Validated and built {output}")


if __name__ == "__main__":
    build()
