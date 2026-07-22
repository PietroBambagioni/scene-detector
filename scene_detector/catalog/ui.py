from __future__ import annotations

import json

_TEMPLATE = """<!doctype html>
<html lang="it">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__ — Catalogo scene</title>
<style>
:root { color-scheme: light dark; }
* { box-sizing: border-box; }
body { margin:0; font: 15px/1.5 -apple-system, system-ui, sans-serif; background:#111; color:#eee; }
@media (prefers-color-scheme: light){ body{ background:#f6f6f6; color:#111; } }
header { display:flex; gap:12px; align-items:center; padding:10px 16px; border-bottom:1px solid #333; position:sticky; top:0; background:inherit; z-index:2; }
header h1 { font-size:16px; margin:0; white-space:nowrap; }
header .meta { color:#888; font-size:13px; white-space:nowrap; }
header .spacer { flex:1; }
input, button, textarea { font:inherit; }
#filter { padding:6px 10px; border-radius:8px; border:1px solid #444; background:transparent; color:inherit; }
button { padding:6px 12px; border-radius:8px; border:1px solid #555; background:#2a2a2a; color:#eee; cursor:pointer; }
@media (prefers-color-scheme: light){ button{ background:#fff; color:#111; } }
#timeline { display:flex; align-items:center; height:40px; padding:0 14px; border-bottom:1px solid #333; position:sticky; top:53px; background:inherit; z-index:2; }
#track { position:relative; flex:1; height:22px; background:rgba(127,127,127,.14); border-radius:5px; }
.pin { position:absolute; top:0; height:100%; width:2px; margin-left:-1px; background:#6b7fa8; cursor:pointer; }
.pin:hover { background:#8ab4ff; width:3px; margin-left:-1.5px; }
.pin.active { background:#508cff; width:3px; margin-left:-1.5px; box-shadow:0 0 0 1px rgba(80,140,255,.6); z-index:1; }
main { display:grid; grid-template-columns: 340px 1fr; height: calc(100vh - 94px); }
#list { overflow:auto; border-right:1px solid #333; }
.item { padding:10px 14px; border-bottom:1px solid #222; cursor:pointer; }
.item:hover { background:rgba(127,127,127,.12); }
.item.sel { background:rgba(80,140,255,.22); }
.item .h { display:flex; justify-content:space-between; color:#8ab4ff; font-size:12px; font-variant-numeric:tabular-nums; }
.item .d { color:#999; font-size:13px; margin-top:2px; max-height:3em; overflow:hidden; }
#detail { padding:16px; overflow:auto; display:flex; flex-direction:column; gap:10px; }
video { width:100%; max-height:52vh; background:#000; border-radius:8px; }
label { font-size:12px; color:#888; text-transform:uppercase; letter-spacing:.04em; }
textarea { width:100%; min-height:70px; padding:8px; border-radius:8px; border:1px solid #444; background:transparent; color:inherit; resize:vertical; }
.nav { display:flex; gap:8px; align-items:center; }
.tc { color:#8ab4ff; font-variant-numeric:tabular-nums; }
#saved { color:#e0a24a; font-size:13px; margin-left:auto; }
#cast { display:flex; gap:10px; overflow-x:auto; padding:8px 14px; border-bottom:1px solid #333; }
#cast:empty { display:none; }
.castcard { flex:0 0 auto; display:flex; flex-direction:column; align-items:center; gap:4px; width:88px; cursor:pointer; padding:4px; border-radius:8px; border:1px solid transparent; }
.castcard:hover { background:rgba(127,127,127,.12); }
.castcard.active { border-color:#508cff; background:rgba(80,140,255,.14); }
.castcard img, .castcard .ph { width:56px; height:56px; border-radius:50%; object-fit:cover; background:#333; display:flex; align-items:center; justify-content:center; color:#8ab4ff; font-size:20px; }
.castcard input { width:100%; text-align:center; font-size:12px; padding:2px 3px; border:1px solid transparent; border-radius:5px; background:transparent; color:inherit; }
.castcard input:hover, .castcard input:focus { border-color:#444; background:rgba(127,127,127,.10); outline:none; }
.castcard .n { color:#888; font-size:11px; }
#chips { display:flex; flex-wrap:wrap; gap:6px; }
.chip { padding:2px 10px; border-radius:12px; background:rgba(80,140,255,.18); color:#8ab4ff; font-size:12px; cursor:pointer; }
.chip:hover { background:rgba(80,140,255,.30); }
</style>
</head>
<body>
<header>
  <h1>__TITLE__</h1>
  <div class="meta" id="meta"></div>
  <div class="spacer"></div>
  <input id="filter" placeholder="cerca nei dialoghi…">
  <button id="export">Export JSON</button>
</header>
<div id="timeline"><div id="track"></div></div>
<div id="cast"></div>
<main>
  <div id="list"></div>
  <div id="detail">
    <video id="player" controls preload="metadata"></video>
    <div class="tc" id="tc"></div>
    <div id="chips"></div>
    <label>Dialogo</label>
    <textarea id="dialogue"></textarea>
    <label>Descrizione</label>
    <textarea id="description" placeholder="(descrizione visiva — da generare)"></textarea>
    <div class="nav">
      <button id="prev">◀ Prec</button>
      <button id="next">Succ ▶</button>
      <span id="saved"></span>
    </div>
  </div>
</main>
<script>
const DATA = __DATA__;
const shots = DATA.shots;
const cast = DATA.cast || [];
const castById = {};
cast.forEach(c => castById[c.id] = c);
let charFilter = null;
let cur = -1;
const $ = id => document.getElementById(id);
const fmt = t => { t = Math.max(0, t|0); const m=(t/60)|0, s=t%60; return m+':'+String(s).padStart(2,'0'); };
const esc = s => s.replace(/[&<>]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));

$('meta').textContent = `${DATA.video} · ${DATA.n_shots} shot · ${DATA.detector}`;

function renderList(filter='') {
  const list = $('list'); list.innerHTML = '';
  shots.forEach((sh, i) => {
    const d = sh.dialogue || '';
    if (filter && !d.toLowerCase().includes(filter)) return;
    if (charFilter !== null && !(sh.characters || []).includes(charFilter)) return;
    const el = document.createElement('div');
    el.className = 'item' + (i===cur ? ' sel' : '');
    el.dataset.i = i;
    el.innerHTML = `<div class="h"><span>#${String(i).padStart(3,'0')}</span><span>${fmt(sh.start_time)}–${fmt(sh.end_time)}</span></div>`
                 + `<div class="d">${d ? esc(d.slice(0,120)) : '<i>—</i>'}</div>`;
    el.onclick = () => select(i);
    list.appendChild(el);
  });
}

function renderTimeline() {
  const track = $('track');
  const total = DATA.duration || (shots.length ? shots[shots.length-1].end_time : 0);
  if (!total) return;
  shots.forEach((sh, i) => {
    const pin = document.createElement('div');
    pin.className = 'pin';
    pin.dataset.i = i;
    pin.style.left = (100 * sh.start_time / total) + '%';
    pin.title = `#${String(i).padStart(3,'0')}  ${fmt(sh.start_time)}–${fmt(sh.end_time)}` + (sh.dialogue ? '  ' + sh.dialogue.slice(0,60) : '');
    pin.onclick = () => select(i);
    track.appendChild(pin);
  });
}

function select(i) {
  if (i < 0 || i >= shots.length) return;
  cur = i;
  const sh = shots[i];
  // con --split-mode none non ci sono clip: si riproduce il film intero a intervallo
  // (media fragment). Il '#t=' va rimesso ogni volta o il player resta sul frammento vecchio.
  const src = sh.clip || `${DATA.video_src}#t=${sh.start_time},${sh.end_time}`;
  $('player').src = src;
  $('tc').textContent = `#${String(i).padStart(3,'0')}  ${fmt(sh.start_time)}–${fmt(sh.end_time)}  (${sh.clip || DATA.video})`;
  renderChips(sh);
  $('dialogue').value = sh.dialogue || '';
  $('description').value = sh.description || '';
  document.querySelectorAll('.item').forEach(e => e.classList.toggle('sel', +e.dataset.i === i));
  document.querySelectorAll('.pin').forEach(e => e.classList.toggle('active', +e.dataset.i === i));
  const sel = document.querySelector('.item.sel'); if (sel) sel.scrollIntoView({block:'nearest'});
}

$('dialogue').addEventListener('input', e => { if (cur>=0) { shots[cur].dialogue = e.target.value; dirty(); }});
$('description').addEventListener('input', e => { if (cur>=0) { shots[cur].description = e.target.value; dirty(); }});
function dirty(){ $('saved').textContent = '● modifiche non esportate'; }

$('prev').onclick = () => select(cur-1);
$('next').onclick = () => select(cur+1);
document.addEventListener('keydown', e => {
  if (e.target.tagName === 'TEXTAREA' || e.target.tagName === 'INPUT') return;
  if (e.key === 'ArrowDown' || e.key === 'j') select(cur+1);
  if (e.key === 'ArrowUp'   || e.key === 'k') select(cur-1);
});
$('filter').addEventListener('input', e => renderList(e.target.value.toLowerCase()));

$('export').onclick = () => {
  const blob = new Blob([JSON.stringify(DATA, null, 2)], {type:'application/json'});
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = (DATA.video || 'catalog').replace(/\\.[^.]+$/, '') + '_catalog.json';
  a.click();
  $('saved').textContent = 'esportato ✓';
};

function renderCast() {
  const el = $('cast'); el.innerHTML = '';
  cast.forEach(c => {
    const card = document.createElement('div');
    card.className = 'castcard' + (charFilter === c.id ? ' active' : '');
    const face = c.thumb ? `<img src="${encodeURI(c.thumb)}" alt="">`
                         : `<div class="ph">${esc((c.name||'?').slice(0,1))}</div>`;
    card.innerHTML = face + `<input value="${esc(c.name)}" title="rinomina personaggio">`
                          + `<span class="n">${c.n_shots} shot</span>`;
    const input = card.querySelector('input');
    input.addEventListener('click', e => e.stopPropagation());
    input.addEventListener('input', e => { c.name = e.target.value; dirty(); if (cur>=0) renderChips(shots[cur]); });
    card.addEventListener('click', () => {
      charFilter = (charFilter === c.id ? null : c.id);
      renderCast(); renderList($('filter').value.toLowerCase());
    });
    el.appendChild(card);
  });
}

function renderChips(sh) {
  const el = $('chips'); el.innerHTML = '';
  (sh.characters || []).forEach(id => {
    const c = castById[id]; if (!c) return;
    const chip = document.createElement('span');
    chip.className = 'chip';
    chip.textContent = c.name;
    chip.title = 'filtra per ' + c.name;
    chip.onclick = () => { charFilter = id; renderCast(); renderList($('filter').value.toLowerCase()); };
    el.appendChild(chip);
  });
}

renderList();
renderTimeline();
renderCast();
select(0);
</script>
</body>
</html>
"""


def build_html(manifest, title=None):
    """Genera la UI HTML self-contained del catalogo dal manifest."""
    data = json.dumps(manifest, ensure_ascii=False).replace("</", "<\\/")
    title = title or manifest.get("video") or "Catalogo scene"
    safe_title = title.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return _TEMPLATE.replace("__DATA__", data).replace("__TITLE__", safe_title)
