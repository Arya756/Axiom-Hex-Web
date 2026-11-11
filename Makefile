# Axiom Evaluation Suite Makefile (Issue #13, A-17)

PYTHON ?= $(shell which .venv/bin/python || which python3 || echo python)
PYTEST ?= $(shell which .venv/bin/pytest || which pytest || echo pytest)

.PHONY: eval build-dataset baseline-runner test-issue13 ci-seed-check

eval: build-dataset baseline-runner test-issue13

build-dataset:
	$(PYTHON) eval/build_dataset.py

baseline-runner:
	$(PYTHON) eval/baseline_runner.py

test-issue13:
	$(PYTEST) tests/test_issue13.py -v

ci-seed-check:
	$(PYTHON) -c "import json, glob, sys; seeds = {json.load(open(f))['id'] for f in glob.glob('eval/seed/*.json')}; gt = {item['id'].split('_mut')[0] for item in json.load(open('eval/ground_truth.json'))}; missing = seeds - gt; sys.exit(f'Seed IDs missing from ground_truth: {missing}') if missing else print(f'All {len(seeds)} seed IDs present in ground_truth.json')"

