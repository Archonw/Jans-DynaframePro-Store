# module.css aus module.src.css bauen: die Schrift Antonio (OFL) wird eingebettet.
# Aufruf: sh build.sh <Ordner mit antonio-latin-400-normal.woff2 und -700->
python3 - "$1" <<'PY'
import base64, sys
from pathlib import Path
css = Path("module.src.css").read_text(encoding="utf-8")
for weight in ("400", "700"):
    font = Path(sys.argv[1]) / f"antonio-latin-{weight}-normal.woff2"
    css = css.replace(f"@@ANTONIO{weight}@@", base64.b64encode(font.read_bytes()).decode())
Path("module.css").write_text(css, encoding="utf-8")
PY
