#!/bin/zsh
# Apple Silicon용 .app 빌드 → dist/ServerTimeClick-mac-arm64.zip
set -euo pipefail
cd "$(dirname "$0")"

[[ -x .venv/bin/python ]] || uv venv --python 3.13 .venv
uv pip install --python .venv/bin/python -q -r requirements.txt pyinstaller

rm -rf build dist
.venv/bin/pyinstaller --noconfirm --windowed \
  --name "ServerTimeClick" \
  --osx-bundle-identifier "com.alexgo.servertimeclick" \
  --target-arch arm64 \
  --add-data "ui.html:." \
  app.py

# 서명 없는 앱이라 ad-hoc 서명만 (손쉬운 사용 권한이 서명에 묶임)
codesign --force --deep --sign - dist/ServerTimeClick.app
ditto -c -k --keepParent dist/ServerTimeClick.app dist/ServerTimeClick-mac-arm64.zip
ls -lh dist/*.zip
