.PHONY: install test lint demo golden bench compare media
install:
	uv venv .venv && uv pip install --python .venv/bin/python -e ".[dev]"
test:
	.venv/bin/python -m pytest --cov=safha --cov-report=term
lint:
	.venv/bin/ruff check .
demo:
	.venv/bin/safha demo
golden:
	.venv/bin/python scripts/update_golden.py
bench:            # CORPUS=dir of PDFs (python bench/fetch_corpus.py CORPUS); the recipes are kept for the two runs after
	.venv/bin/safha bench $(CORPUS) -o bench/results/bench.json --book-jobs 4 --jobs 4 --recipes bench/work/recipes
	.venv/bin/safha bench $(CORPUS) -o bench/results/bench-compact.json --book-jobs 4 --jobs 4 --recipes bench/work/recipes --compact
	.venv/bin/python bench/rule_audit.py $(CORPUS) bench/work/recipes
compare:          # CORPUS as above, after bench/install_tools.sh
	bench/compare.sh $(CORPUS) bench/work/compare
media:
	.venv/bin/python scripts/make_media.py bench/work/compare docs/media
