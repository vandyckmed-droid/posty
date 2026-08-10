# ETF momentum screen. Requires FMP_API_KEY (Financial Modeling Prep).
#
#   make all        full refresh, roughly 10 minutes on a cold cache
#   make page       rebuild the page from data already downloaded
#   make preview    render the built page in Chromium and assert it works
#
# Data lands in ./data (override with ETF_DATA). Fetch stages are resumable:
# completed symbol files are skipped, so re-running retries only failures.

export PYTHONPATH := pipeline
DATA ?= $(or $(ETF_DATA),data)
PAGE := $(DATA)/etf-momentum.build.html
PY   := python3

.PHONY: all fetch page preview analysis clean distclean

all: fetch page

fetch:
	$(PY) pipeline/01_universe.py
	$(PY) pipeline/02_history.py hist
	$(PY) pipeline/03_screen.py
	$(PY) pipeline/02_history.py adj

page:
	$(PY) pipeline/04_score.py
	$(PY) pipeline/05_corr.py
	$(PY) pipeline/06_page.py

preview: $(PAGE)
	node tools/preview.mjs $(PAGE) $(DATA)

analysis:
	$(PY) analysis/correlation_report.py $(TICKERS)

# Derived artefacts only; downloaded bars are kept.
clean:
	rm -f $(DATA)/ranked.json $(DATA)/liquid.json $(PAGE)

# Everything, including the downloaded history.
distclean:
	rm -rf $(DATA)
