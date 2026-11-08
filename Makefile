# Settings come from .env when it exists, so `make run` matches the app.
-include .env

PYTHON := ./.venv/bin/python
UVICORN := ./.venv/bin/uvicorn
APP := app.main:app
HOST := $(or $(SWANN_APP_HOST),127.0.0.1)
PORT := $(or $(SWANN_APP_PORT),8750)
PIDFILE := .uvicorn.pid
API_STATUS := /api/status

MCP_VENV := ./.venv-mcp

.PHONY: help setup run dev stop check backup mcp-setup mcp

help:
	@echo "make setup  install everything into .venv"
	@echo "make dev    run the server in this terminal, reloading on edits"
	@echo "make run    run the server in the background"
	@echo "make stop   stop the background server"
	@echo "make check  check the recorder answers"
	@echo "make backup save every recorder setting to a file"
	@echo "make mcp-setup install the MCP server, so an LLM can drive it"
	@echo "make mcp    run the MCP server by hand, to check it starts"

setup:
	@command -v ffmpeg >/dev/null 2>&1 || { \
	  echo "ffmpeg is missing. Install it first:"; \
	  echo "  mac:    brew install ffmpeg"; \
	  echo "  ubuntu: sudo apt install ffmpeg"; \
	  exit 1; }
	python3 -m venv .venv
	./.venv/bin/pip install --upgrade pip
	./.venv/bin/pip install -e .
	@if [ ! -f .env ]; then cp .env.example .env; echo; \
	  echo "Made .env for you. Open it and put in your recorder's"; \
	  echo "address and password, then run: make check"; \
	else echo; echo "Kept your .env. Next: make check"; fi

dev:
	$(UVICORN) $(APP) --host $(HOST) --port $(PORT) --reload

run: stop
	@$(UVICORN) $(APP) --host $(HOST) --port $(PORT) > .uvicorn.log 2>&1 & echo $$! > $(PIDFILE)
	@printf "starting"; \
	for i in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15; do \
	  if curl -fsS -o /dev/null --max-time 2 2>/dev/null http://$(HOST):$(PORT)$(API_STATUS); then \
	    echo " ok"; echo "running on http://$(HOST):$(PORT)/health"; exit 0; fi; \
	  printf "."; sleep 1; \
	done; \
	echo " failed"; tail -20 .uvicorn.log; exit 1

stop:
	@if [ -f $(PIDFILE) ]; then kill `cat $(PIDFILE)` 2>/dev/null; rm -f $(PIDFILE); fi
	@pids=`lsof -ti tcp:$(PORT) 2>/dev/null`; \
	if [ -n "$$pids" ]; then kill $$pids 2>/dev/null; \
	  printf "stopping"; \
	  for i in 1 2 3 4 5 6 7 8 9 10; do \
	    left=`lsof -ti tcp:$(PORT) 2>/dev/null`; \
	    if [ -z "$$left" ]; then echo " stopped"; exit 0; fi; \
	    printf "."; sleep 1; \
	  done; \
	  left=`lsof -ti tcp:$(PORT) 2>/dev/null`; \
	  if [ -n "$$left" ]; then kill -9 $$left 2>/dev/null; echo " forced"; fi; \
	else echo "not running"; fi

check:
	$(PYTHON) -m scripts.check_recorder

backup:
	$(PYTHON) -m scripts.backup_settings

# The MCP server lives in its own virtual environment, because the MCP
# library wants a newer Starlette than FastAPI allows.
mcp-setup:
	python3 -m venv $(MCP_VENV)
	$(MCP_VENV)/bin/pip install --upgrade pip
	$(MCP_VENV)/bin/pip install "mcp==2.3.0" "httpx==0.28.1"
	chmod +x mcp_server/run.sh
	@echo "now run: claude mcp add swann --scope local -- $(PWD)/mcp_server/run.sh"

mcp:
	./mcp_server/run.sh
