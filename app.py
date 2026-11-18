"""매크로 GUI. 실행: .venv/bin/python app.py"""
import ctypes
import json
import pathlib
import sys
import threading
import time

import webview

import macro

# .app 번들로 묶이면 리소스는 _MEIPASS, 설정은 번들 밖(쓰기 가능)에 둔다
HERE = pathlib.Path(getattr(sys, "_MEIPASS", pathlib.Path(__file__).parent))
DATA = pathlib.Path.home() / "Library/Application Support/ServerTimeClick" if getattr(sys, "frozen", False) else HERE
DATA.mkdir(parents=True, exist_ok=True)
STEPS_FILE = DATA / "steps.txt"
STATE_FILE = DATA / ".macro_state.json"  # 마지막 시각·URL


def accessibility_ok(prompt=False):
    """손쉬운 사용 권한이 없으면 클릭이 조용히 무시된다.
    prompt=True면 macOS 권한 요청 창을 띄워 앱을 목록에 자동 추가한다."""
    try:
        import objc
        from Foundation import NSDictionary
        lib = ctypes.cdll.LoadLibrary("/System/Library/Frameworks/ApplicationServices.framework/ApplicationServices")
        lib.AXIsProcessTrustedWithOptions.restype = ctypes.c_bool
        lib.AXIsProcessTrustedWithOptions.argtypes = [ctypes.c_void_p]
        opts = NSDictionary.dictionaryWithObject_forKey_(prompt, "AXTrustedCheckOptionPrompt")
        return lib.AXIsProcessTrustedWithOptions(objc.pyobjc_id(opts))
    except (OSError, ImportError, AttributeError):
        return True  # 확인 불가 → 경고하지 않음


class Api:
    def __init__(self):
        self._window = None
        self._cancel = threading.Event()

    def load(self):
        state = json.loads(STATE_FILE.read_text()) if STATE_FILE.exists() else {}
        try:
            steps = macro.parse_steps(STEPS_FILE.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            steps = [(0, 0, 1, 0, 0)]
        return {
            "steps": steps,
            "at": state.get("at", ""),
            "url": state.get("url", macro.DEFAULT_URL),
            "early": state.get("early", 0),
            "axOk": accessibility_ok(prompt=True),
        }

    def ax_status(self):
        return accessibility_ok()

    def sync(self, url):
        try:
            offset, rtt = macro.measure_offset(url)
            return {"offset": offset, "rtt": rtt}
        except Exception as e:
            return {"error": f"서버 시간을 가져오지 못했습니다: {e}"}

    def pick(self):
        time.sleep(3)
        import pyautogui
        x, y = pyautogui.position()
        return [int(x), int(y)]

    def arm(self, at, steps, url, early):
        try:
            steps = macro.parse_steps(macro.format_steps(steps))
            target = macro.parse_target(at)
        except ValueError as e:
            return {"error": str(e)}
        STEPS_FILE.write_text(macro.format_steps(steps), encoding="utf-8")
        STATE_FILE.write_text(json.dumps({"at": at, "url": url, "early": early}))
        res = self.sync(url)
        if "error" in res:
            return res
        self._cancel.clear()
        threading.Thread(target=self._run, args=(steps, target, res["offset"], early), daemon=True).start()
        return {**res, "target": target}

    def cancel(self):
        self._cancel.set()

    def _run(self, steps, target, offset, early):
        try:
            ok = macro.run(steps, target, offset, early, log=self._log, cancel=self._cancel)
        except Exception as e:  # FAILSAFE(마우스 모서리) 포함
            self._log(f"중단됨: {e}")
            ok = False
        self._js("onDone", ok)

    def _log(self, msg):
        self._js("onLog", msg)

    def _js(self, fn, arg):
        self._window.evaluate_js(f"{fn}({json.dumps(arg, ensure_ascii=False)})")


if __name__ == "__main__":
    api = Api()
    api._window = webview.create_window(
        "서버시간 클릭", html=(HERE / "ui.html").read_text(encoding="utf-8"), js_api=api,
        width=440, height=680, min_size=(400, 560),
    )
    webview.start()
