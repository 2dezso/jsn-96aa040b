"""Build the published site from site/src into site/public.

Same substitutions as the prototypes: /*@include name*/ pulls in site/src/lib/name,
and __DATA__ is replaced with data/site.json. Refuses to build if the pipeline's
checks failed, so wrong numbers never go live.
"""
import json
import re
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC, LIB, OUT = HERE / "src", HERE / "src" / "lib", HERE / "public"
data = (HERE.parent / "data" / "site.json").read_text(encoding="utf-8")
checks = json.loads(data)["checks"]
if any(checks.values()):
    sys.exit(f"not building: pipeline checks failed {checks}")


def expand(text):
    return re.sub(r"/\*@include ([\w.-]+)\*/", lambda m: (LIB / m.group(1)).read_text(encoding="utf-8"), text)


shutil.rmtree(OUT, ignore_errors=True)
OUT.mkdir()
for src in sorted(SRC.glob("*.html")):
    (OUT / src.name).write_text(expand(src.read_text(encoding="utf-8")).replace("__DATA__", data), encoding="utf-8")
    print("built", src.name)
(OUT / "robots.txt").write_text("User-agent: *\nDisallow: /\n", encoding="utf-8")
(OUT / ".nojekyll").write_text("", encoding="utf-8")
