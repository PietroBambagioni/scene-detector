#!/bin/sh
# Il PDF si rigenera da qui, con lo stesso comando di sempre: se cambia il markdown il PDF
# va rifatto a mano, e senza questo file la ricetta si perde nella cronologia della shell.
# xelatex e non pdflatex: il testo è pieno di «», ×, ÷ e accenti.
cd "$(dirname "$0")"
PATH="/Library/TeX/texbin:$PATH" pandoc "Come è stato fatto.md" \
  -o "Come è stato fatto.pdf" --pdf-engine=xelatex --toc --toc-depth=2 \
  -V lang=it -V geometry:margin=2.5cm -V fontsize=11pt \
  -V mainfont="Georgia" -V monofont="Menlo" -V monofontoptions="Scale=0.85" \
  -V linkcolor=black -V colorlinks=true
ls -l "Come è stato fatto.pdf"
