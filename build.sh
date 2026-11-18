#!/bin/zsh
# Apple Silicon용 .app 빌드 → dist/ServerTimeClick-mac-arm64.zip
set -euo pipefail
cd "$(dirname "$0")"

[[ -x .venv/bin/python ]] || uv venv --python 3.13 .venv
uv pip install --python .venv/bin/python -q -r requirements.txt pyinstaller

rm -rf build dist 2>/dev/null || { sleep 2; rm -rf build dist; }  # Finder/종료 중인 앱이 잡고 있으면 재시도
.venv/bin/pyinstaller --noconfirm --windowed \
  --name "ServerTimeClick" \
  --osx-bundle-identifier "com.alexgo.servertimeclick" \
  --target-arch arm64 \
  --add-data "ui.html:." \
  app.py

# 손쉬운 사용 권한은 서명에 묶인다.
# 키체인에 자체 서명 인증서가 있으면 그걸로 서명 → 재빌드해도 권한 유지.
# 없으면 ad-hoc 서명 → 빌드마다 권한을 다시 켜야 함.
SIGN_ID="${SIGN_ID:-ServerTimeClick Self-Signed}"
if security find-certificate -c "$SIGN_ID" >/dev/null 2>&1; then
  codesign --force --deep --sign "$SIGN_ID" dist/ServerTimeClick.app
else
  echo "경고: '$SIGN_ID' 인증서 없음 → ad-hoc 서명" >&2
  codesign --force --deep --sign - dist/ServerTimeClick.app
fi
codesign -dr - dist/ServerTimeClick.app 2>&1 | tail -1
ditto -c -k --keepParent dist/ServerTimeClick.app dist/ServerTimeClick-mac-arm64.zip
ls -lh dist/*.zip
