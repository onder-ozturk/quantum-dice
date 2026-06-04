TEX=paper
# IEEEtran two-column class compiles with pdflatex + bibtex (IEEEtran.bst).
LATEX=pdflatex -interaction=nonstopmode -halt-on-error

.PHONY: all bib clean

all:
	$(LATEX) $(TEX).tex

bib:
	$(LATEX) $(TEX).tex
	bibtex $(TEX)
	$(LATEX) $(TEX).tex
	$(LATEX) $(TEX).tex

clean:
	rm -f $(TEX).aux $(TEX).bbl $(TEX).blg $(TEX).log $(TEX).out $(TEX).toc
