import glob
import os
from datetime import datetime

_LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__ or ""))), "log")
_LOG_PATH = os.path.join(_LOG_DIR, f"debug_{datetime.now().strftime('%Y-%m-%dT%H-%M-%S')}.log")
_MAX_LOGS = 10


def _setup_log() -> None:
    try:
        os.makedirs(_LOG_DIR, exist_ok=True)
        logs = sorted(glob.glob(os.path.join(_LOG_DIR, "debug_*.log")))
        for old in logs[:-(_MAX_LOGS - 1)]:
            os.remove(old)
    except Exception:
        pass


_setup_log()


def log(msg: str) -> None:
    try:
        with open(_LOG_PATH, "a") as f:
            f.write(f"[ip-switch] {msg}\n")
    except Exception:
        pass
