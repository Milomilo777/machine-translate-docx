# Makefile — local task runner for machine-translate-docx
#
# Created in C4 of the 2026-05-10 architecture cleanup. Replaces the
# ad-hoc memorized ``E:/Python311/python.exe -m pytest tests/ ...`` lines.
#
# Default target prints the help. Run ``make help`` or ``make`` to see
# the list. Native Windows users without GNU make can use the matching
# ``tasks.bat`` shim — same target names.
#
# All paths are relative to the repository root. The Python interpreter
# defaults to whatever is on ``$PATH``; override with
# ``PYTHON=E:/Python311/python.exe make test`` if you have multiple.

PYTHON ?= python
FIXTURE := tests/fixtures/sample_hyperlink.docx
TMPDIR  := _real_test

.PHONY: help test test-integration test-all smoke live-deepl live-google live-all clean

help:
	@echo "machine-translate-docx — local task runner"
	@echo ""
	@echo "  make test              pytest unit tests (excludes live + integration + v2 e2e)"
	@echo "  make test-integration  opt-in pytest of tests/integration/ (slower, no network)"
	@echo "  make test-all          unit + integration tests in one shot"
	@echo "  make smoke             DeepL en->fr quick run on the fixture"
	@echo "  make live-deepl        DeepL en->fr + en->fa real-file runs"
	@echo "  make live-google       Google en->fr + en->fa real-file runs"
	@echo "  make live-all          all real-file runs (DeepL + Google, 4 outputs)"
	@echo "  make clean             remove $(TMPDIR)/ and any *.pyc"
	@echo ""
	@echo "Override the interpreter:"
	@echo "  PYTHON=E:/Python311/python.exe make test"

test:
	$(PYTHON) -m pytest tests/ --ignore=tests/test_v2_e2e.py --ignore=tests/integration

# T-2 (2026-05-11): opt-in integration target. tests/integration/ is
# kept out of the default `make test` because some files there spin
# up subprocesses or expect a long runtime; this target is meant for
# the CI matrix and manual runs.
test-integration:
	$(PYTHON) -m pytest tests/integration --ignore=tests/test_v2_e2e.py

test-all: test test-integration

smoke: $(TMPDIR)
	cp $(FIXTURE) $(TMPDIR)/smoke.docx
	cd $(TMPDIR) && PYTHONPATH=../src $(PYTHON) -m machine_translate_docx.cli \
		--docxfile smoke.docx \
		--srclang en --destlang fr \
		--engine deepl --enginemethod phrasesblock \
		--silent --exitonsuccess
	@echo "smoke: $(TMPDIR)/smoke_FRE_Deepl.docx"

live-deepl: $(TMPDIR)
	cp $(FIXTURE) $(TMPDIR)/deepl_fr.docx
	cd $(TMPDIR) && PYTHONPATH=../src $(PYTHON) -m machine_translate_docx.cli \
		--docxfile deepl_fr.docx \
		--srclang en --destlang fr \
		--engine deepl --enginemethod phrasesblock \
		--silent --exitonsuccess
	cp $(FIXTURE) $(TMPDIR)/deepl_fa.docx
	cd $(TMPDIR) && PYTHONPATH=../src $(PYTHON) -m machine_translate_docx.cli \
		--docxfile deepl_fa.docx \
		--srclang en --destlang fa \
		--engine deepl --enginemethod phrasesblock \
		--silent --exitonsuccess

live-google: $(TMPDIR)
	cp $(FIXTURE) $(TMPDIR)/google_fr.docx
	cd $(TMPDIR) && PYTHONPATH=../src $(PYTHON) -m machine_translate_docx.cli \
		--docxfile google_fr.docx \
		--srclang en --destlang fr \
		--engine google --enginemethod phrasesblock \
		--silent --exitonsuccess
	cp $(FIXTURE) $(TMPDIR)/google_fa.docx
	cd $(TMPDIR) && PYTHONPATH=../src $(PYTHON) -m machine_translate_docx.cli \
		--docxfile google_fa.docx \
		--srclang en --destlang fa \
		--engine google --enginemethod phrasesblock \
		--silent --exitonsuccess

live-all: live-deepl live-google

$(TMPDIR):
	@mkdir -p $(TMPDIR)

clean:
	rm -rf $(TMPDIR)
	find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
