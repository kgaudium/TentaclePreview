import os
import stat
import shutil
import time
from TentaclePreview import output


def safe_rmtree(path: str, max_attempts: int = 3, delay: float = 0.2) -> bool:
    if not os.path.exists(path):
        return True

    def remove_readonly(func, path, _):
        try:
            os.chmod(path, stat.S_IWRITE | stat.S_IREAD | 0o777)
            func(path)
        except Exception:
            time.sleep(delay)
            func(path)

    for attempt in range(max_attempts):
        try:
            shutil.rmtree(path, onerror=remove_readonly)
            return True
        except Exception as e:
            output.log(f"Attempt {attempt + 1} failed to delete {path}: {e}", "warning")
            if attempt < max_attempts - 1:
                time.sleep(delay)
    return False