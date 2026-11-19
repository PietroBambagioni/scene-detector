"""Il transcript JSONL della sessione in un documento leggibile."""
import json, re, sys
from pathlib import Path
from datetime import datetime, timezone

SRC = Path(sys.argv[1]); OUT = Path(sys.argv[2])

def pulisci(t):
    t = re.sub(r'<system-reminder>.*?</system-reminder>', '', t, flags=re.S)
    t = re.sub(r'<command-name>.*?</command-message>', '', t, flags=re.S)
    t = re.sub(r'<local-command-stdout>.*?</local-command-stdout>', '', t, flags=re.S)
    return t.strip()

def sintesi(nome, inp):
    if nome == "Bash":
        c = (inp.get("command") or "").strip()
        d = inp.get("description") or ""
        prima = c.split("\n")[0][:150]
        return f"`{prima}{'…' if len(c) > 150 else ''}`" + (f" — {d}" if d else "")
    if nome in ("Write", "Edit"):
        return f"scrive `{Path(inp.get('file_path','?')).name}`"
    if nome == "Read":
        return f"legge `{Path(inp.get('file_path','?')).name}`"
    if nome.startswith("mcp__claude-in-chrome__"):
        breve = nome.replace("mcp__claude-in-chrome__", "")
        if breve == "javascript_tool":
            js = (inp.get("text") or "").strip().split("\n")[0][:100]
            return f"browser · esegue JS: `{js}…`"
        return f"browser · {breve}" + (f" → {inp['url']}" if inp.get("url") else "")
    if nome == "Artifact":
        return f"pubblica artifact ({inp.get('action','publish')})"
    if nome == "AskUserQuestion":
        return "**pone una domanda**"
    return nome

righe = []
for linea in SRC.read_text().splitlines():
    try:
        d = json.loads(linea)
    except Exception:
        continue
    tipo = d.get("type")
    msg = d.get("message") or {}
    cont = msg.get("content")
    if tipo == "user":
        testo = cont if isinstance(cont, str) else " ".join(
            b.get("text", "") for b in cont if isinstance(b, dict) and b.get("type") == "text")
        testo = pulisci(testo)
        if testo and not testo.startswith("[Request interrupted"):
            righe.append(("user", testo, d.get("timestamp")))
    elif tipo == "assistant" and isinstance(cont, list):
        for b in cont:
            if not isinstance(b, dict):
                continue
            if b.get("type") == "text" and b.get("text", "").strip():
                righe.append(("claude", b["text"].strip(), d.get("timestamp")))
            elif b.get("type") == "tool_use":
                righe.append(("tool", sintesi(b.get("name",""), b.get("input") or {}), None))

fuori = ["# Anna nel *Fuori campo* — diario della sessione\n",
         f"Trascrizione della conversazione del 25 agosto 2026, dal transcript di "
         f"Claude Code. Gli output dei comandi e le immagini non sono riportati; delle azioni "
         f"resta il comando in sintesi.\n\n---\n"]
n_turni = 0
buffer_tool = []
def scarica_tool():
    global buffer_tool, fuori
    if buffer_tool:
        fuori.append("<details><summary>" + str(len(buffer_tool)) + " azioni</summary>\n")
        fuori += ["- " + t for t in buffer_tool]
        fuori.append("\n</details>\n")
        buffer_tool = []

for chi, testo, ts in righe:
    if chi == "tool":
        buffer_tool.append(testo)
        continue
    scarica_tool()
    if chi == "user":
        n_turni += 1
        # i timestamp del transcript sono in UTC: mostrarli così sposta tutto di due ore
        quando = ""
        if ts:
            loc = datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone()
            quando = f" · {loc:%H:%M}"
        fuori.append(f"\n## {n_turni}. Pietro{quando}\n\n> " + testo.replace("\n", "\n> ") + "\n")
    else:
        testo = re.sub(r"^(#{1,3}) ", r"#\1 ", testo, flags=re.M)
        fuori.append("\n**Claude:**\n\n" + testo + "\n")
scarica_tool()

OUT.write_text("\n".join(fuori))
print(f"{OUT}  ·  {n_turni} turni  ·  {len(righe)} blocchi  ·  {OUT.stat().st_size/1024:.0f} KB")
