#!/bin/bash
source .venv/bin/activate 2>/dev/null || true
python3 test_all_models.py
