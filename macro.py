"""서버 시각(HTTP Date 헤더) 기준으로 지정 시각에 좌표를 순차/연타 클릭한다.

    python macro.py --selftest
    python macro.py --pos
    python macro.py --at 20:00:00 --steps steps.txt [--url https://www.naver.com] [--early 0]
"""
import argparse
import datetime as dt
import http.client
import statistics
import threading
import time
import urllib.parse
from email.utils import parsedate_to_datetime

DEFAULT_URL = "https://www.naver.com"


# ---------- 서버 시각 ----------

class Probe:
    """keep-alive 연결로 HEAD를 보내 (보낸 시각, 받은 시각, 서버 초)를 돌려준다."""

    def __init__(self, url):
        u = urllib.parse.urlsplit(url if "://" in url else "https://" + url)
        self.host, self.path = u.netloc, u.path or "/"
        self.cls = http.client.HTTPSConnection if u.scheme == "https" else http.client.HTTPConnection
        self.conn = None

    def __call__(self):
        for attempt in (0, 1):  # 서버가 연결을 끊으면 한 번 재연결
            try:
                if self.conn is None:
                    self.conn = self.cls(self.host, timeout=3)
                    self.conn.connect()  # 핸드셰이크는 측정 밖에서
                t0 = time.time()
                self.conn.request("HEAD", self.path, headers={"Cache-Control": "no-cache"})
                r = self.conn.getresponse()
                r.read()
                t1 = time.time()
                date = r.getheader("Date")
                if not date:
                    raise RuntimeError(f"{self.host} 응답에 Date 헤더가 없습니다")
                return t0, t1, parse_date(date)
            except (http.client.HTTPException, OSError):
                self.close()
                if attempt:
                    raise

    def close(self):
        if self.conn:
            self.conn.close()
        self.conn = None


def parse_date(header):
    return int(parsedate_to_datetime(header).timestamp())


def measure_offset(url=DEFAULT_URL, samples=3, gap=0.01):
    """서버 시각 - 내 시계 (초)와 평균 RTT(초)를 돌려준다.

    Date 헤더는 1초 단위라, 초가 바뀌는 순간을 잡아 ms 단위로 추정한다.
    정초는 '이전 응답 중간점'과 '다음 응답 중간점' 사이 → 그 가운데로 잡는다.
    """
    probe = Probe(url)
    offsets, rtts = [], []
    try:
        prev = probe()
        while len(offsets) < samples:
            if offsets:  # 다음 정초 150ms 전까지 쉰다 (요청 수 절약)
                nxt = int(time.time() + offsets[-1]) + 1 - offsets[-1]
                time.sleep(max(0.0, nxt - time.time() - 0.15))
                prev = probe()
            cur = probe()
            while cur[2] == prev[2]:
                time.sleep(gap)
                prev, cur = cur, probe()
            if cur[2] != prev[2] + 1:  # 1초 넘게 건너뛰면 버리고 다시
                prev = cur
                continue
            mid_a = (prev[0] + prev[1]) / 2
            mid_b = (cur[0] + cur[1]) / 2
            offsets.append(cur[2] - (mid_a + mid_b) / 2)
            rtts.append(cur[1] - cur[0])
            prev = cur
    finally:
        probe.close()
    return statistics.median(offsets), statistics.mean(rtts)


# ---------- 단계 / 시각 ----------

def parse_steps(text):
    """한 줄 = 'x y 횟수 연타간격ms 다음단계까지ms'. 뒤 세 값은 생략 가능 (1 0 0)."""
    steps = []
    for n, line in enumerate(text.splitlines(), 1):
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        nums = [int(v) for v in line.split()]
        if not 2 <= len(nums) <= 5:
            raise ValueError(f"{n}번째 줄: 값은 2~5개여야 합니다 → {line!r}")
        x, y, count, interval, after = (nums + [1, 0, 0])[:5]
        if count < 1 or interval < 0 or after < 0:
            raise ValueError(f"{n}번째 줄: 횟수는 1 이상, 간격은 0 이상이어야 합니다")
        steps.append((x, y, count, interval, after))
    if not steps:
        raise ValueError("클릭 단계가 없습니다")
    return steps


def format_steps(steps):
    head = "# x y 횟수 연타간격ms 다음단계까지ms\n"
    return head + "".join(" ".join(map(str, s)) + "\n" for s in steps)


def parse_target(text, now=None):
    """'HH:MM:SS[.mmm]' → 그 시각의 epoch. 이미 지났으면 다음 날."""
    t = dt.time.fromisoformat(text.strip())
    now = now or dt.datetime.now()
    target = dt.datetime.combine(now.date(), t)
    if target <= now:
        target += dt.timedelta(days=1)
    return target.timestamp()


def schedule(steps, first_click):
    """각 클릭의 (시각, x, y, 단계번호, 몇번째, 횟수) 목록."""
    plan, t = [], first_click
    for i, (x, y, count, interval, after) in enumerate(steps, 1):
        for k in range(1, count + 1):
            plan.append((t, x, y, i, k, count))
            if k < count:
                t += interval / 1000
        t += after / 1000
    return plan


def wait_until(t, cancel):
    """t(로컬 epoch)까지 대기. 마지막 30ms는 busy-wait. 취소되면 False."""
    while True:
        rem = t - time.time()
        if cancel.is_set():
            return False
        if rem <= 0:
            return True
        if rem > 0.03:
            time.sleep(min(rem - 0.03, 0.2))


def run(steps, target, offset, early_ms=0, log=print, cancel=None):
    """target(서버 기준 epoch)에 첫 클릭. log(문자열)로 진행 보고."""
    import pyautogui
    pyautogui.PAUSE = 0  # 기본값 0.1초 지연 제거. FAILSAFE(마우스를 화면 모서리로)는 유지
    cancel = cancel or threading.Event()
    first = target - offset - early_ms / 1000
    for t, x, y, i, k, count in schedule(steps, first):
        if not wait_until(t, cancel):
            log("취소됨")
            return False
        pyautogui.click(x, y)
        log(f"{fmt(time.time() + offset)}  {i}단계 ({x}, {y})  {k}/{count}")
    log("실행 완료")
    return True


def fmt(epoch):
    return dt.datetime.fromtimestamp(epoch).strftime("%H:%M:%S.%f")[:-3]


# ---------- CLI ----------

def selftest():
    utc = dt.datetime(2026, 11, 18, 15, 49, 16, tzinfo=dt.timezone.utc).timestamp()
    assert parse_date("Wed, 18 Nov 2026 15:49:16 GMT") == utc
    assert parse_steps("812 430 10 50 300\n# c\n\n900 500") == [(812, 430, 10, 50, 300), (900, 500, 1, 0, 0)]
    assert parse_steps(format_steps([(1, 2, 3, 4, 5)])) == [(1, 2, 3, 4, 5)]
    for bad in ("1", "1 2 0", "", "1 2 3 4 5 6"):
        try:
            parse_steps(bad)
            raise AssertionError(bad)
        except ValueError:
            pass
    now = dt.datetime(2026, 11, 19, 12, 0, 0)
    assert parse_target("13:00:00.250", now) == dt.datetime(2026, 11, 19, 13, 0, 0, 250000).timestamp()
    assert parse_target("11:00", now) == dt.datetime(2026, 11, 20, 11, 0).timestamp()
    plan = schedule([(1, 1, 3, 50, 300), (2, 2, 1, 0, 0)], 100.0)
    assert [round(p[0] - 100, 3) for p in plan] == [0, 0.05, 0.1, 0.4]
    assert wait_until(time.time() + 0.05, threading.Event())
    print("selftest ok")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--at", help="첫 클릭 시각 (서버 기준) HH:MM:SS[.mmm]")
    ap.add_argument("--steps", default="steps.txt")
    ap.add_argument("--url", default=DEFAULT_URL)
    ap.add_argument("--early", type=int, default=0, help="N ms 일찍 클릭")
    ap.add_argument("--pos", action="store_true", help="3초 뒤 마우스 좌표 출력")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()

    if a.selftest:
        return selftest()
    if a.pos:
        import pyautogui
        time.sleep(3)
        return print(*pyautogui.position())
    if not a.at:
        ap.error("--at 이 필요합니다")

    steps = parse_steps(open(a.steps, encoding="utf-8").read())
    target = parse_target(a.at)
    offset, rtt = measure_offset(a.url)
    print(f"서버 - 내 시계 {offset * 1000:+.0f}ms, 왕복 {rtt * 1000:.0f}ms")
    print(f"첫 클릭 {fmt(target)} (서버 기준), {target - time.time() - offset:.1f}초 남음. 취소: Ctrl+C")
    try:
        run(steps, target, offset, a.early)
    except KeyboardInterrupt:
        print("취소됨")


if __name__ == "__main__":
    main()
