from __future__ import annotations

import json
from pathlib import Path

_TEMPLATE = """<!doctype html>
<html lang="it">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Cataloghi scene</title>
<style>
:root { color-scheme: light dark; }
* { box-sizing: border-box; }
body { margin:0; font: 15px/1.5 -apple-system, system-ui, sans-serif; background:#111; color:#eee; }
@media (prefers-color-scheme: light){ body{ background:#f6f6f6; color:#111; } }
header { display:flex; gap:12px; align-items:baseline; padding:16px 20px; border-bottom:1px solid #333; }
header h1 { font-size:18px; margin:0; }
header .meta { color:#888; font-size:13px; }
header .spacer { flex:1; }
#filter { padding:6px 10px; border-radius:8px; border:1px solid #444; background:transparent; color:inherit; font:inherit; }
main { display:grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap:14px; padding:20px; }
a.card { display:block; text-decoration:none; color:inherit; padding:14px; border:1px solid #333; border-radius:12px; background:rgba(127,127,127,.06); transition:border-color .12s, background .12s; }
a.card:hover { border-color:#508cff; background:rgba(80,140,255,.10); }
.card .title { font-size:16px; font-weight:600; margin:0 0 8px; word-break:break-word; }
.card .row { display:flex; justify-content:space-between; color:#999; font-size:13px; font-variant-numeric:tabular-nums; }
.card .det { display:inline-block; margin-top:8px; padding:1px 8px; border-radius:6px; background:rgba(80,140,255,.18); color:#8ab4ff; font-size:12px; }
.empty { padding:40px 20px; color:#888; }
</style>
</head>
<body>
<header>
  <h1>Cataloghi scene</h1>
  <div class="meta" id="meta"></div>
  <div class="spacer"></div>
  <input id="filter" placeholder="cerca film…">
</header>
<main id="grid"></main>
<script>
const DATA = __DATA__;
const $ = id => document.getElementById(id);
const esc = s => String(s).replace(/[&<>]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));
const fmtDur = t => {
  t = Math.max(0, t|0); const h=(t/3600)|0, m=((t%3600)/60)|0, s=t%60;
  const mm=String(m).padStart(2,'0'), ss=String(s).padStart(2,'0');
  return h ? `${h}:${mm}:${ss}` : `${m}:${ss}`;
};

$('meta').textContent = `${DATA.length} film`;

function render(filter='') {
  const grid = $('grid'); grid.innerHTML = '';
  const items = DATA.filter(c => !filter || c.video.toLowerCase().includes(filter));
  if (!items.length) {
    grid.innerHTML = '<div class="empty">Nessun catalogo.</div>';
    return;
  }
  items.forEach(c => {
    const a = document.createElement('a');
    a.className = 'card';
    a.href = encodeURIComponent(c.dir) + '/index.html';
    a.innerHTML = `<div class="title">${esc(c.video)}</div>`
                + `<div class="row"><span>${c.n_shots} shot</span><span>${fmtDur(c.duration)}</span></div>`
                + `<span class="det">${esc(c.detector)}</span>`;
    grid.appendChild(a);
  });
}

$('filter').addEventListener('input', e => render(e.target.value.toLowerCase()));
render();
</script>
</body>
</html>
"""


def scan_catalogs(out_dir):
    """Scandisce `<out>/*/manifest.json` → lista cataloghi ordinata per nome film.

    Ignora le sotto-cartelle senza `manifest.json` o con manifest illeggibile.
    Ogni voce: dir (nome cartella), video, n_shots, duration, detector.
    """
    out_dir = Path(out_dir)
    catalogs = []
    for manifest_path in sorted(out_dir.glob("*/manifest.json")):
        try:
            m = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        catalogs.append({
            "dir": manifest_path.parent.name,
            "video": m.get("video") or manifest_path.parent.name,
            "n_shots": m.get("n_shots", 0),
            "duration": m.get("duration", 0),
            "detector": m.get("detector", "?"),
        })
    catalogs.sort(key=lambda c: c["video"].lower())
    return catalogs


def build_index_html(catalogs):
    """Genera la galleria HTML self-contained dai cataloghi."""
    data = json.dumps(catalogs, ensure_ascii=False).replace("</", "<\\/")
    return _TEMPLATE.replace("__DATA__", data)


def write_gallery(out_dir):
    """Scandisce `<out>`, scrive `<out>/index.html`, restituisce (path, n_cataloghi)."""
    out_dir = Path(out_dir)
    catalogs = scan_catalogs(out_dir)
    index_path = out_dir / "index.html"
    index_path.write_text(build_index_html(catalogs), encoding="utf-8")
    return index_path, len(catalogs)
