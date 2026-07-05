.PHONY: test test-unit test-behavior test-live-model test-cloud-evals test-private-ocr-evals setup smoke-ollama seed-scratch-db dev-api dev-web web-install web-build agent-chat-ui-typecheck e2e-agent-chat-ui e2e e2e-private-week

PYTHON ?= $(shell [ -x .venv/bin/python ] && echo .venv/bin/python || echo python3)

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

test-private-ocr-evals:
	PRIVATE_OCR_EVALS=true PYTHONPATH=src $(PYTHON) -m unittest discover -s tests/live -p 'test_private_label_ocr_evals.py'

smoke-ollama:
	PYTHONPATH=src $(PYTHON) -m health_monitor smoke-ollama --timeout-seconds 10

setup:
	$(PYTHON) -m pip install -e .

seed-scratch-db:
	PYTHONPATH=src $(PYTHON) scripts/seed_scratch_db.py --sqlite-path $${SQLITE_PATH:-data/scratch/health-monitor.sqlite3} --overwrite

dev-api:
	@if [ "$${AGENT_RUNTIME:-pydantic-ai}" = "pydantic-ai" ] && [ "$${REQUIRE_MODEL:-true}" != "false" ]; then \
		$(PYTHON) -c "import pydantic_ai" || (echo 'pip install pydantic-ai with `make setup` (or your venv pip) before running dev-api' >&2; exit 1); \
	else \
		true; \
	fi
	PYTHONPATH=src $(PYTHON) -m health_monitor api --host 127.0.0.1 --port 8765 & \
	API_PID=$$!; \
	PYTHONPATH=src $(PYTHON) -m health_monitor worker --interval-seconds 5 & \
	WORKER_PID=$$!; \
	trap 'kill $$API_PID $$WORKER_PID 2>/dev/null' EXIT INT TERM; \
	wait

dev-web:
	cd web && bun run dev

web-install:
	cd web && bun install

web-build:
	cd web && bun run build

agent-chat-ui-typecheck:
	web/node_modules/.bin/tsc -p packages/agent-chat-ui/tsconfig.json --noEmit

e2e-agent-chat-ui:
	cd web && bun run e2e:agent-chat-ui

e2e:
	cd web && bun run e2e

e2e-private-week:
	@echo "Private week replay e2e is deferred during the chat-first UX redesign."
