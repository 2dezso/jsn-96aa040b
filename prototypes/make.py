"""Build each prototype in src/ into out/.

Two substitutions: /*@include name*/ pulls in src/lib/name (shared components),
and __DATA__ is replaced with data/site.json.
"""
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
LIB = HERE / "src" / "lib"
OUT = HERE / "out"
OUT.mkdir(exist_ok=True)
data = (HERE.parent / "data" / "site.json").read_text(encoding="utf-8")
json.loads(data)  # fail early if the data file is broken


def expand(text):
    return re.sub(r"/\*@include ([\w.-]+)\*/", lambda m: (LIB / m.group(1)).read_text(encoding="utf-8"), text)


for src in sorted((HERE / "src").glob("*.html")):
    (OUT / src.name).write_text(expand(src.read_text(encoding="utf-8")).replace("__DATA__", data), encoding="utf-8")
    print("built", src.name)
