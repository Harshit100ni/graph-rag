SHELL := /bin/bash

# -------- Config --------
VENV := .venv
PY := $(VENV)/bin/python
PIP := $(VENV)/bin/pip

# Load env vars from .env if present
ifneq (,$(wildcard .env))
include .env
export
endif

# -------- Targets --------
.PHONY: help venv install run vectors cards clean

help:
	@echo "make venv        # create venv"
	@echo "make install     # pip install -r requirements.txt"
	@echo "make run         # start API (uvicorn)"
	@echo "make vectors     # build/refresh embeddings via LangChain Neo4jVector"
	@echo "make cards       # regenerate node 'card' text (Cypher)"
	@echo "make clean       # remove venv and pycache"

venv:
	python3 -m venv $(VENV)
	$(PIP) install --upgrade pip

install: venv
	$(PIP) install -r requirements.txt

run:
	$(PY) -m uvicorn app.main:app --reload --port 8000

# Rebuild embeddings & ensure the native vector index exists
vectors:
	OPENAI_API_KEY="$(OPENAI_API_KEY)" \
	NEO4J_URI="$(NEO4J_URI)" \
	NEO4J_USER="$(NEO4J_USER)" \
	NEO4J_PASS="$(NEO4J_PASS)" \
	EMB_MODEL="$(EMB_MODEL)" \
	VECTOR_INDEX="$(VECTOR_INDEX)" \
	$(PY) -m scripts.bootstrap_vectors

# OPTIONAL: regenerate concise 'card' text for all nodes (uses APOC)
cards:
	@if [ -z "$$NEO4J_USER" ] || [ -z "$$NEO4J_PASS" ]; then \
	  echo "Set NEO4J_USER and NEO4J_PASS in your environment or .env"; exit 1; fi
	@echo "Regenerating cards..."
	cypher-shell -a "$(NEO4J_URI)" -u "$(NEO4J_USER)" -p "$(NEO4J_PASS)" -f scripts/refresh_cards.cypher

clean:
	rm -rf $(VENV) **/__pycache__ .pytest_cache
