from __future__ import annotations

import html
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
button:disabled { opacity:.35; cursor:default; }
@media (prefers-color-scheme: light){ button{ background:#fff; color:#111; } }
#timeline { display:flex; align-items:center; height:40px; padding:0 14px; border-bottom:1px solid #333; position:sticky; top:53px; background:inherit; z-index:2; }
#track { position:relative; flex:1; height:22px; background:rgba(127,127,127,.14); border-radius:5px; }
#bands { position:absolute; inset:0; border-radius:5px; overflow:hidden; }
.band { position:absolute; top:0; height:100%; cursor:pointer; }
.band.alt { background:rgba(127,127,127,.18); }
.band.cur { background:rgba(80,140,255,.30); }
.pin { position:absolute; top:0; height:100%; width:2px; margin-left:-1px; background:#6b7fa8; cursor:pointer; }
.pin:hover { background:#8ab4ff; width:3px; margin-left:-1.5px; }
.pin.active { background:#508cff; width:3px; margin-left:-1.5px; box-shadow:0 0 0 1px rgba(80,140,255,.6); z-index:1; }
main { display:grid; grid-template-columns: 340px 1fr; height: calc(100vh - 94px); }
#list { overflow:auto; border-right:1px solid #333; }
.item { display:flex; gap:9px; padding:8px 14px; border-bottom:1px solid #222; cursor:pointer; }
.item img { width:58px; height:33px; object-fit:cover; border-radius:4px; background:#222; flex:0 0 auto; }
.item .c { flex:1; min-width:0; }
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
/* volto che il rilevatore non riconosce come umano: mostrato, ma dichiarato inaffidabile */
.castcard.unc img, .castcard.unc .ph { opacity:.45; }
.castcard.unc .n { color:#e0a24a; }
/* terzo livello: le scene raggruppano gli shot nella sidebar */
.scene { border-bottom:1px solid #2a2a2a; }
.sh { display:flex; gap:9px; align-items:flex-start; padding:8px 10px; cursor:pointer; }
.sh:hover { background:rgba(127,127,127,.10); }
.scene.cur > .sh { background:rgba(80,140,255,.12); }
.sh .chev { color:#8ab4ff; flex:0 0 14px; font-size:13px; line-height:1.3; text-align:center; padding:2px 0; }
.sh .chev:hover { color:#fff; }
.sh img { width:92px; height:52px; object-fit:cover; border-radius:5px; background:#222; flex:0 0 auto; }
.sh .b { flex:1; min-width:0; }
.sh .t { display:flex; justify-content:space-between; gap:8px; color:#8ab4ff; font-size:12px; font-variant-numeric:tabular-nums; }
.sh .who, .sh .q { font-size:11px; color:#888; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.sh .q { color:#999; font-size:12px; margin-top:1px; }
.acts { display:flex; gap:4px; margin-top:4px; }
.acts button { padding:0 7px; font-size:11px; border-radius:5px; }
.shots { display:none; }
.scene.open .shots { display:block; }
.scene .item { padding-left:22px; }
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
<div id="timeline"><div id="track"><div id="bands"></div></div></div>
<div id="cast"></div>
<main>
  <div id="list"></div>
  <div id="detail">
    <video id="player" controls preload="metadata"></video>
    <div class="tc" id="tc"></div>
    <div class="nav">
      <button id="fprev" title="un fotogramma indietro">◀ 1f</button>
      <span class="tc" id="frame"></span>
      <button id="fnext" title="un fotogramma avanti">1f ▶</button>
      <button id="split" title="spezza questo shot al fotogramma sul player">✂ taglia qui</button>
      <button id="mergeprev" title="fondi questo shot nel precedente">⤴ unisci al prec</button>
    </div>
    <div id="chips"></div>
    <label id="dlgLabel">Dialogo</label>
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
// Senza `--scenes` il manifest non ha la chiave: `scenes` resta null e ogni ramo qui sotto
// ricade sul comportamento a due livelli. E' opt-in, quindi e' il caso piu' comune.
const scenes = DATA.scenes || null;
const open = new Set();          // scene espanse: si apre quella corrente, le altre restano chiuse
let playing = null;              // riproduzione di una scena su clip separate: {sc, i}
let charFilter = null;
let cur = -1;
const $ = id => document.getElementById(id);
const fmt = t => { t = Math.max(0, t|0); const m=(t/60)|0, s=t%60; return m+':'+String(s).padStart(2,'0'); };
const esc = s => s.replace(/[&<>]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));

// funzione e non riga secca: unisci/dividi cambiano il conteggio delle scene
function renderMeta() {
  $('meta').textContent = `${DATA.video} · ${DATA.n_shots} shot`
    + (scenes ? ` · ${scenes.length} scene` : '') + ` · ${DATA.detector}`;
}

// Con --split-mode none non ci sono clip: si riproduce il film originale spostando currentTime,
// non riassegnando src a ogni click. Il media fragment #t= era inaffidabile — cambiare solo il
// frammento non fa ricaricare, e ricaricare 2,7 GB a ogni click e' comunque lento. Qui il film
// si carica UNA volta, poi ogni shot e' un seek + play che si ferma a fine shot.
const FILM = DATA.video_src || null;
let stopAt = Infinity;
if (FILM) {
  $('player').src = FILM;
  $('player').addEventListener('timeupdate', () => {
    if ($('player').currentTime >= stopAt) $('player').pause();
  });
  // `stopAt` vincola *la riproduzione che abbiamo avviato noi*, non il player: appena l'utente
  // interviene va disarmato, altrimenti il timeupdate rimette in pausa e il film sembra rotto.
  // Due interventi, due casi, ed e' il secondo quello che si nota:
  //  - seek sulla barra oltre lo shot corrente -> ripartirebbe in pausa
  //  - play a fine shot (siamo fermi *su* stopAt) -> non riparte affatto, nessun seek di mezzo
  // Niente flag da tenere in sincrono: basta guardare dove si trova la testina.
  $('player').addEventListener('seeked', () => {
    const sh = shots[cur], t = $('player').currentTime;
    if (!sh || t < sh.start_time || t > sh.end_time) stopAt = Infinity;
  });
  $('player').addEventListener('play', () => {
    if ($('player').currentTime >= stopAt) stopAt = Infinity;
  });
}

function seekTo(sh) {
  const p = $('player');
  stopAt = sh.end_time;
  const go = () => { p.currentTime = sh.start_time; p.play().catch(() => {}); };
  if (p.readyState >= 1) go();                 // metadati pronti: seek subito
  else p.addEventListener('loadedmetadata', go, { once: true });
}

// ----------------------------------------------------------------- scene ---
// Le scene sono una vista *sopra* gli shot: `cur` resta un indice di shot, non cambia sistema
// di coordinate. Ogni funzione qui sotto e' inerte quando `scenes` e' null.

function sceneOf(i) {
  if (!scenes) return -1;
  for (let s = 0; s < scenes.length; s++)
    if (i >= scenes[s].first_shot && i <= scenes[s].last_shot) return s;
  return -1;
}

function sceneCast(sc) {
  const n = {};
  for (let i = sc.first_shot; i <= sc.last_shot; i++)
    (shots[i].characters || []).forEach(id => n[id] = (n[id]||0) + 1);
  return Object.entries(n).sort((a,b) => b[1]-a[1]).slice(0,3)
    .map(([id]) => (castById[id]||{}).name).filter(Boolean);
}

function sceneLine(sc) {
  for (let i = sc.first_shot; i <= sc.last_shot; i++)
    if (shots[i].dialogue) return shots[i].dialogue;
  return '';
}

// I confini automatici sono giusti circa una volta su tre (F1 0,30 contro 0,63 di accordo fra
// annotatori umani): senza queste due correzioni la struttura sarebbe da guardare e basta.
function mergeWithPrev(si) {
  if (si <= 0) return;
  scenes[si-1].last_shot = scenes[si].last_shot;
  scenes.splice(si, 1);
  afterEdit(si - 1);
}

function splitAt(i) {            // lo shot `i` diventa l'inizio di una scena nuova
  const si = sceneOf(i);
  if (si < 0 || i <= scenes[si].first_shot) return;
  scenes.splice(si + 1, 0, { index:0, first_shot:i, last_shot:scenes[si].last_shot,
                             start_frame:0, end_frame:0, start_time:0, end_time:0 });
  scenes[si].last_shot = i - 1;
  afterEdit(si + 1);
}

function renumberScenes() {
  scenes.forEach((sc, i) => {
    sc.index = i;
    sc.start_frame = shots[sc.first_shot].start_frame;
    sc.end_frame   = shots[sc.last_shot].end_frame;
    sc.start_time  = shots[sc.first_shot].start_time;
    sc.end_time    = shots[sc.last_shot].end_time;
  });
  DATA.n_scenes = scenes.length;
  renderMeta();
  checkScenes();
}

// Le scene sono contigue e coprono tutti gli shot: e' lo stesso contratto dei range di frame nel
// resto del progetto, ed e' la classe di bug che qui si paga cara. Meglio in console che dentro
// un export silenziosamente rotto.
function checkScenes() {
  if (!scenes || !scenes.length) return true;
  let ok = scenes[0].first_shot === 0 && scenes[scenes.length-1].last_shot === shots.length - 1;
  scenes.forEach((sc, i) => {
    if (sc.last_shot < sc.first_shot) ok = false;
    if (i && sc.first_shot !== scenes[i-1].last_shot + 1) ok = false;
  });
  if (!ok) console.error('scene non contigue o non complete', scenes);
  return ok;
}

function afterEdit(si) {
  renumberScenes();
  open.clear(); open.add(si);    // gli indici sono cambiati: il set vecchio non vuol piu' dire niente
  dirty();
  renderList($('filter').value.toLowerCase());
  renderTimeline();
  select(Math.min(Math.max(cur, 0), shots.length - 1));
}

function playScene(sc) {
  select(sc.first_shot);
  if (FILM) seekTo(sc);          // seekTo legge solo start_time/end_time: la scena e' uno shot lungo
  else if (shots[sc.first_shot].clip) {
    playing = { sc, i: sc.first_shot };
    $('player').play().catch(() => {});
  }
}

// clip su disco: la scena e' una playlist, si avanza a fine clip finche' si resta dentro
$('player').addEventListener('ended', () => {
  if (!playing || playing.i >= playing.sc.last_shot) { playing = null; return; }
  playing.i += 1;
  select(playing.i);
  $('player').play().catch(() => {});
});

// ------------------------------------------------------------------- shot ---
// Gli shot sono l'unico livello dove l'unita' e' il **frame**, non un indice: il confine lo
// detta la testina del player, non una riga della lista. `currentTime` e' relativo alla clip
// quando le clip esistono e al film quando non ci sono — l'offset e' lo start_frame dello shot.

function frameBase() { const sh = shots[cur]; return sh && sh.clip ? sh.start_frame : 0; }
function frameNow() { return frameBase() + Math.floor($('player').currentTime * DATA.fps); }

// Mezzo frame dentro: cosi' il `floor` di `frameNow` ridà esattamente `f` invece di inciampare
// sull'arrotondamento del confine.
function goToFrame(f) {
  const p = $('player'); p.pause();
  p.currentTime = (f - frameBase() + 0.5) / DATA.fps;
}

function renderFrame() {
  const sh = shots[cur], f = frameNow();
  // Il range accanto al frame non e' decorazione: il taglio deve cadere **dentro** lo shot e non
  // sul suo primo frame (li' non spezzerebbe niente), e i due modi di finirci fuori non si
  // vedono da soli — selezionare uno shot lascia la testina sul primo frame, e lasciar scorrere
  // la ferma a `end_time`, che e' **un frame oltre** l'ultimo. Senza il range il bottone sembra
  // spento a caso.
  $('frame').textContent = sh ? `frame ${f} · shot ${sh.start_frame}–${sh.end_frame}` : `frame ${f}`;
  $('split').disabled = !sh || f <= sh.start_frame || f > sh.end_frame;
  $('split').title = $('split').disabled
    ? 'porta la testina dentro lo shot (non sul primo frame) per poter tagliare'
    : `spezza lo shot: ${sh.start_frame}–${f-1} + ${f}–${sh.end_frame}`;
  $('mergeprev').disabled = cur <= 0;
}
$('player').addEventListener('timeupdate', renderFrame);
$('player').addEventListener('seeked', renderFrame);

// `end_frame` e' inclusivo (core/scene.py) e `end_time` e' `(end_frame + 1) / fps`: il frame `f`
// apre il secondo shot, quindi il primo si chiude a `f - 1` e i due tempi coincidono su `f/fps`.
function splitShotAt(f) {
  const sh = shots[cur];
  if (f <= sh.start_frame || f > sh.end_frame) return;
  // Descrizione e dialogo vanno a **entrambi** i figli. Dopo un taglio manuale sono comunque da
  // rifare, ma perderli in silenzio e' il danno gia' pagato una volta (manifest.py,
  // CAMPI_COSTOSI). `thumb` e `clip` puntano ancora a quelli del padre: li rifa' il ritaglio.
  const nuovo = { ...sh, start_frame: f, end_frame: sh.end_frame,
                  start_time: f / DATA.fps, end_time: sh.end_time, confidence: null };
  delete nuovo.transition;          // la giunta apriva il padre, non il figlio
  sh.end_frame = f - 1;
  sh.end_time = f / DATA.fps;
  shots.splice(cur + 1, 0, nuovo);
  // gli indici a valle slittano di uno; la scena che conteneva `cur` ha uno shot in piu'
  if (scenes) scenes.forEach(sc => {
    if (sc.first_shot > cur) sc.first_shot++;
    if (sc.last_shot >= cur) sc.last_shot++;
  });
  afterShotEdit(cur + 1);
}

function mergeShotWithPrev(i) {
  if (i <= 0) return;
  const a = shots[i-1], b = shots[i];
  a.end_frame = b.end_frame;
  a.end_time = b.end_time;
  const unisci = (x, y) => [x, y].filter(Boolean).join(' ');
  a.dialogue = unisci(a.dialogue, b.dialogue);
  a.description = unisci(a.description, b.description);
  a.characters = [...new Set([...(a.characters || []), ...(b.characters || [])])];
  if (a.speakers || b.speakers)
    a.speakers = [...new Set([...(a.speakers || []), ...(b.speakers || [])])];
  shots.splice(i, 1);
  if (scenes) {
    scenes.forEach(sc => {
      if (sc.first_shot > i) sc.first_shot--;
      if (sc.last_shot >= i) sc.last_shot--;
    });
    // fondere oltre il confine di scena puo' svuotare una scena fatta del solo shot `i`: va
    // tolta, altrimenti resta un range vuoto e `checkScenes` si lamenta a ragione
    for (let s = scenes.length - 1; s >= 0; s--)
      if (scenes[s].last_shot < scenes[s].first_shot) scenes.splice(s, 1);
  }
  afterShotEdit(i - 1);
}

function afterShotEdit(i) {
  shots.forEach((sh, k) => sh.index = k);
  DATA.n_shots = shots.length;
  if (scenes) renumberScenes(); else renderMeta();   // renumberScenes ridisegna gia' la meta
  dirty();
  renderList($('filter').value.toLowerCase());
  renderTimeline();
  select(Math.min(Math.max(i, 0), shots.length - 1));
}

// ------------------------------------------------------------------ lista ---

function shotRow(i) {
  const sh = shots[i], d = sh.dialogue || '';
  const el = document.createElement('div');
  el.className = 'item' + (i===cur ? ' sel' : '');
  el.dataset.i = i;
  // la miniatura c'e' solo con `--scenes` (le estrae quello step): senza, la riga resta di testo
  el.innerHTML = (sh.thumb ? `<img src="${encodeURI(sh.thumb)}" alt="" loading="lazy">` : '')
               + `<div class="c"><div class="h"><span>#${String(i).padStart(3,'0')}</span>`
               + `<span>${fmt(sh.start_time)}–${fmt(sh.end_time)}</span></div>`
    // col trattino "nessun dialogo" la riga cresce di 16px per non dire niente: con la
    // miniatura il vuoto si vede gia'
               + (d ? `<div class="d">${esc(d.slice(0,120))}</div>`
                    : (sh.thumb ? '' : '<div class="d"><i>—</i></div>')) + `</div>`;
  el.onclick = () => { playing = null; select(i); };
  return el;
}

function sceneHeader(sc, si, n) {
  const th = shots[sc.first_shot].thumb;
  const who = sceneCast(sc), line = sceneLine(sc);
  const el = document.createElement('div');
  el.className = 'sh';
  el.innerHTML = `<span class="chev">${open.has(si) ? '▾' : '▸'}</span>`
    + (th ? `<img src="${encodeURI(th)}" alt="" loading="lazy">` : '')
    + `<div class="b"><div class="t"><span>Scena ${String(si+1).padStart(2,'0')}</span>`
    + `<span>${fmt(sc.start_time)}–${fmt(sc.end_time)}</span></div>`
    + `<div class="who">${n} shot${who.length ? ' · ' + esc(who.join(', ')) : ''}</div>`
    + (line ? `<div class="q">${esc(line.slice(0,90))}</div>` : '')
    + `<div class="acts"></div></div>`;
  el.querySelector('.chev').onclick = e => {
    e.stopPropagation();
    open.has(si) ? open.delete(si) : open.add(si);
    renderList($('filter').value.toLowerCase());
  };
  const acts = el.querySelector('.acts');
  if (si > 0) acts.appendChild(actBtn('⤴ unisci', 'unisci alla scena precedente', () => mergeWithPrev(si)));
  if (cur > sc.first_shot && cur <= sc.last_shot)
    acts.appendChild(actBtn('✂ dividi', `nuova scena a partire da #${String(cur).padStart(3,'0')}`,
                            () => splitAt(cur)));
  el.onclick = () => playScene(sc);
  return el;
}

function actBtn(label, title, fn) {
  const b = document.createElement('button');
  b.textContent = label; b.title = title;
  b.onclick = e => { e.stopPropagation(); fn(); };
  return b;
}

function renderList(filter='') {
  const list = $('list'); list.innerHTML = '';
  const shown = i => {
    const d = shots[i].dialogue || '';
    if (filter && !d.toLowerCase().includes(filter)) return false;
    if (charFilter !== null && !(shots[i].characters || []).includes(charFilter)) return false;
    return true;
  };
  if (!scenes) { shots.forEach((_, i) => { if (shown(i)) list.appendChild(shotRow(i)); }); return; }

  const filtering = !!filter || charFilter !== null;
  scenes.forEach((sc, si) => {
    const kids = [];
    for (let i = sc.first_shot; i <= sc.last_shot; i++) if (shown(i)) kids.push(i);
    if (!kids.length) return;                       // scena senza superstiti: sparisce dal filtro
    // col filtro attivo si espande: nascondere i risultati dentro scene chiuse sarebbe assurdo
    const isOpen = open.has(si) || filtering;
    const box = document.createElement('div');
    box.className = 'scene' + (isOpen ? ' open' : '') + (sceneOf(cur) === si ? ' cur' : '');
    box.appendChild(sceneHeader(sc, si, kids.length));
    // le righe di una scena chiusa non si costruiscono: `select` ridisegna la lista a ogni
    // spostamento, e su 3200 shot crearle tutte a ogni freccia si sente
    if (isOpen) {
      const inner = document.createElement('div');
      inner.className = 'shots';
      kids.forEach(i => inner.appendChild(shotRow(i)));
      box.appendChild(inner);
    }
    list.appendChild(box);
  });
}

function renderTimeline() {
  const track = $('track'), bands = $('bands');
  track.querySelectorAll('.pin').forEach(e => e.remove());   // ridisegnata dopo ogni modifica
  bands.innerHTML = '';
  const total = DATA.duration || (shots.length ? shots[shots.length-1].end_time : 0);
  if (!total) return;
  if (scenes) scenes.forEach((sc, si) => {
    const b = document.createElement('div');
    b.className = 'band' + (si % 2 ? ' alt' : '');
    b.dataset.s = si;
    b.style.left = (100 * sc.start_time / total) + '%';
    b.style.width = (100 * (sc.end_time - sc.start_time) / total) + '%';
    b.title = `Scena ${String(si+1).padStart(2,'0')}  ${fmt(sc.start_time)}–${fmt(sc.end_time)}`;
    b.onclick = () => playScene(sc);
    bands.appendChild(b);
  });
  shots.forEach((sh, i) => {
    const pin = document.createElement('div');
    pin.className = 'pin';
    pin.dataset.i = i;
    pin.style.left = (100 * sh.start_time / total) + '%';
    pin.title = `#${String(i).padStart(3,'0')}  ${fmt(sh.start_time)}–${fmt(sh.end_time)}` + (sh.dialogue ? '  ' + sh.dialogue.slice(0,60) : '');
    pin.onclick = () => { playing = null; select(i); };
    track.appendChild(pin);
  });
}

function select(i) {
  if (i < 0 || i >= shots.length) return;
  cur = i;
  const sh = shots[i];
  // clip su disco: una src per shot. Film non tagliato: seek sul film gia' caricato.
  if (sh.clip) { stopAt = Infinity; $('player').src = sh.clip; }
  else if (FILM) seekTo(sh);
  $('tc').textContent = `#${String(i).padStart(3,'0')}  ${fmt(sh.start_time)}–${fmt(sh.end_time)}  (${sh.clip || DATA.video})`;
  renderFrame();                 // il `seeked` arriva dopo: intanto i bottoni dicono il vero
  renderChips(sh);
  // `--diarize` è opt-in: senza, `speakers` non c'è e l'etichetta resta quella di sempre. Gli id
  // sono numeri perché la diarizzazione non sa i nomi — il linking speaker↔personaggio non c'è
  // ancora (plan/DA-FARE.md §5, Fase 2).
  const spk = sh.speakers || [];
  $('dlgLabel').textContent = spk.length ? `Dialogo · parlanti ${spk.map(s => 'S' + s).join(', ')}`
                                         : 'Dialogo';
  $('dialogue').value = sh.dialogue || '';
  $('description').value = sh.description || '';
  const si = sceneOf(i);
  // la lista si ridisegna se cambia cosa deve mostrare: scena da aprire, o pulsante dividi da
  // spostare sulla scena corrente
  if (scenes && si >= 0) { open.add(si); renderList($('filter').value.toLowerCase()); }
  document.querySelectorAll('.item').forEach(e => e.classList.toggle('sel', +e.dataset.i === i));
  document.querySelectorAll('.pin').forEach(e => e.classList.toggle('active', +e.dataset.i === i));
  document.querySelectorAll('.band').forEach(e => e.classList.toggle('cur', +e.dataset.s === si));
  const sel = document.querySelector('.item.sel'); if (sel) sel.scrollIntoView({block:'nearest'});
}

$('dialogue').addEventListener('input', e => { if (cur>=0) { shots[cur].dialogue = e.target.value; dirty(); }});
$('description').addEventListener('input', e => { if (cur>=0) { shots[cur].description = e.target.value; dirty(); }});
function dirty(){ $('saved').textContent = '● modifiche non esportate'; }

$('prev').onclick = () => select(cur-1);
$('next').onclick = () => select(cur+1);
$('fprev').onclick = () => goToFrame(frameNow() - 1);
$('fnext').onclick = () => goToFrame(frameNow() + 1);
$('split').onclick = () => splitShotAt(frameNow());
$('mergeprev').onclick = () => mergeShotWithPrev(cur);
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
    card.className = 'castcard' + (charFilter === c.id ? ' active' : '') + (c.uncertain ? ' unc' : '');
    const face = c.thumb ? `<img src="${encodeURI(c.thumb)}" alt="">`
                         : `<div class="ph">${esc((c.name||'?').slice(0,1))}</div>`;
    // `uncertain`: il rilevatore non lo dà per volto umano (droidi, elmetti). Cluster cosi'
    // fondono personaggi diversi, quindi il nome non vale — ed e' escluso dal prompt del VLM.
    card.innerHTML = face + `<input value="${esc(c.name)}" title="rinomina personaggio">`
                          + `<span class="n" title="${c.uncertain ? 'volto non riconosciuto come umano: questo gruppo puo\\' contenere personaggi diversi, ed e\\' escluso dalle descrizioni' : ''}">`
                          + `${c.uncertain ? '⚠ ' : ''}${c.n_shots} shot</span>`;
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

renderMeta();
checkScenes();
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
    return _TEMPLATE.replace("__DATA__", data).replace("__TITLE__", html.escape(title))
