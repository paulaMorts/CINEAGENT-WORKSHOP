#!/bin/bash
# Run CineAgent using the virtual environment (Python 3.13)
# This avoids the ContextVar bug in Python 3.9

cd "$(dirname "$0")"
.venv/bin/python3 -m chainlit run app/main.py "$@"
