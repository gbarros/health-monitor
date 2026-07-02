.PHONY: test test-unit test-behavior test-live-model test-cloud-evals dev-api dev-web web-install web-build e2e

PYTHON ?= python3

test:
	PYTHONPATH=src $(PYTHON) -m unittest discover -s tests -p 'test_*.py'

test-unit:
	PYTHONPATH=src $(PYTHON) -m unittest discover -s tests/unit -p 'test_*.py'

test-behavior:
	PYTHONPATH=src $(PYTHON) -m unittest discover -s tests/behavior -p 'test_*.py'

test-live-model:
	LIVE_MODEL_TESTS=true PYTHONPATH=src $(PYTHON) -m unittest discover -s tests/live -p 'test_*.py'

test-cloud-evals:
	CLOUD_MODEL_CALLS_ENABLED=true PYTHONPATH=src $(PYTHON) -m unittest discover -s tests/live -p 'test_cloud_*.py'

dev-api:
	PYTHONPATH=src $(PYTHON) -m health_monitor api --host 127.0.0.1 --port 8765

dev-web:
	cd web && bun run dev

web-install:
	cd web && bun install

web-build:
	cd web && bun run build

e2e:
	cd web && bun run e2e
