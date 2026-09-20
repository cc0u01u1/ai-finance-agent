#!/bin/bash
# Start the Pydantic AI Web UI
./.venv/bin/uvicorn app:app --reload --port 8000
