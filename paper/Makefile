TEX=paper

.PHONY: all bib clean

all:
	lualatex -interaction=nonstopmode -halt-on-error $(TEX).tex

bib:
	lualatex -interaction=nonstopmode -halt-on-error $(TEX).tex
	bibtex $(TEX)
	lualatex -interaction=nonstopmode -halt-on-error $(TEX).tex
	lualatex -interaction=nonstopmode -halt-on-error $(TEX).tex

clean:
	rm -f $(TEX).aux $(TEX).bbl $(TEX).blg $(TEX).log $(TEX).out $(TEX).toc
