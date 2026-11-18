#!/bin/zsh
# 더블클릭으로 GUI 실행
cd "$(dirname "$0")" && exec .venv/bin/python app.py
