# Requires FMP_API_KEY (Financial Modeling Prep).
#
#   make all           full ETF refresh, roughly 10 minutes on a cold cache
#   make page          rebuild the ETF page from data already downloaded
#   make preview       render the built ETF page in Chromium and assert it works
#
#   make groups        the self-designed stock groups, end to end (~15 min cold)
#   make groups-page   rebuild the groups page from data already downloaded
#   make groups-preview
#
# Data lands in ./data (override with ETF_DATA). Fetch stages are resumable:
# completed symbol files are skipped, so re-running retries only failures.

export PYTHONPATH := pipeline
DATA ?= $(or $(ETF_DATA),data)
PAGE := $(DATA)/etf-momentum.build.html
PY   := python3

# The stock build is a separate product on the same plumbing, with its own data
# directory so the two never collide.
GDATA ?= data-stocks
GPAGE := $(GDATA)/stock-groups.build.html
GENV  := ETF_DATA=$(GDATA) PYTHONPATH=groups:pipeline

.PHONY: all fetch page preview analysis clean distclean \
        groups groups-fetch groups-page groups-preview groups-clean

all: fetch page

fetch:
	$(PY) pipeline/01_universe.py
	$(PY) pipeline/02_history.py hist
	$(PY) pipeline/03_screen.py
	$(PY) pipeline/02_history.py adj
	$(PY) pipeline/04_profile.py
	$(PY) pipeline/05_holdings.py

page:
	$(PY) pipeline/06_score.py
	$(PY) pipeline/07_corr.py
	$(PY) pipeline/08_page.py

preview: $(PAGE)
	node tools/preview.mjs $(PAGE) $(DATA)

analysis:
	$(PY) analysis/correlation_report.py $(TICKERS)

groups: groups-fetch groups-page groups-preview

groups-fetch:
	$(GENV) $(PY) groups/01_universe.py
	$(GENV) $(PY) groups/02_history.py
	$(GENV) $(PY) groups/03_screen.py

groups-page:
	$(GENV) $(PY) groups/04_group.py
	$(GENV) $(PY) groups/05_score.py
	$(GENV) $(PY) groups/06_page.py

groups-preview: $(GPAGE)
	node tools/preview-groups.mjs $(GPAGE) $(GDATA)

# Derived artefacts only; downloaded bars are kept.
clean:
	rm -f $(DATA)/ranked.json $(DATA)/liquid.json $(PAGE)

groups-clean:
	rm -f $(GDATA)/ranked.json $(GDATA)/groups.json $(GDATA)/liquid.json $(GPAGE)

# Everything, including the downloaded history.
distclean:
	rm -rf $(DATA)
