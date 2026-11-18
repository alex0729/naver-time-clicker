# naver-time-clicker

네이버(또는 지정한 서버)의 HTTP `Date` 헤더로 서버 시각을 ms 단위로 추정하고, 지정 시각에 화면 좌표를 순차·연타 클릭하는 macOS 앱.

## 사용자용 설치 (Apple Silicon Mac)

1. [Releases](../../releases/latest)에서 `ServerTimeClick-mac-arm64.zip`을 받아 압축을 푼다.
2. `ServerTimeClick.app`을 응용 프로그램 폴더로 옮긴다.
3. 처음 열 때 "확인되지 않은 개발자" 또는 "손상되었습니다" 경고가 뜨면 터미널에서 실행한다:
   ```sh
   xattr -dr com.apple.quarantine /Applications/ServerTimeClick.app
   ```
   이후 앱을 다시 연다. (서명·공증되지 않은 개인 배포 앱이라 생기는 경고)
4. 손쉬운 사용 권한 요청 창이 뜨면 `시스템 설정 열기` → `ServerTimeClick`을 켠다 → 앱을 종료 후 다시 연다.

### 사용법

1. 앱을 열면 자동으로 서버 시각을 맞춘다. 다른 서비스 기준이 필요하면 `고급 설정 > 기준 서버`에 주소를 넣고 `동기화`.
2. `위치`를 누르고 3초 안에 마우스를 클릭할 곳에 올려 좌표를 찍는다.
3. 단계마다 횟수, 연타 간격, 다음 단계까지 간격(ms)을 넣는다.
4. 첫 클릭 시각(`20:00:00.000`)을 넣고 `예약`. 클릭할 앱 창은 미리 앞에 띄워 둔다.
5. 멈추려면 `취소`를 누르거나 마우스를 화면 모서리로 민다.

## 개발자용

### 설치

```sh
uv venv --python 3.13 .venv
uv pip install --python .venv/bin/python -r requirements.txt
```

- 시스템 설정 > 개인정보 보호 및 보안 > 손쉬운 사용에서 실행하는 터미널을 허용해야 클릭이 동작한다.

### 실행

- GUI: `서버시간 클릭.command` 더블클릭, 또는 `.venv/bin/python app.py`
- CLI:

```sh
.venv/bin/python macro.py --selftest                     # 자체 점검
.venv/bin/python macro.py --pos                          # 3초 뒤 마우스 좌표 출력
.venv/bin/python macro.py --at 20:00:00 --steps steps.txt [--url https://www.naver.com] [--early 0]
```

### steps.txt

한 줄에 한 단계: `x y 횟수 연타간격ms 다음단계까지ms` (뒤 세 값 생략 시 `1 0 0`)

```
812 430 10 50 300
900 500
```

### 동작 원리

- keep-alive 연결로 `HEAD` 요청을 반복해 `Date` 헤더의 초가 바뀌는 순간을 잡는다.
- 정초 시각 = 바뀌기 전·후 응답의 왕복 중간점 사이 가운데. 3회 측정 중앙값을 오프셋으로 쓴다.
- 목표 시각 30ms 전부터 busy-wait로 대기 후 클릭한다.

## 주의

- 마우스를 화면 모서리로 밀면 즉시 중단된다 (pyautogui FAILSAFE).
- 비활성 창의 첫 클릭은 창 활성화에만 쓰일 수 있다. 대상 앱을 미리 앞에 둔다.
- 티켓팅·한정판 구매 등에 쓰면 서비스 약관 위반이 될 수 있다.
