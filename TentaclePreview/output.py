import sys
from datetime import datetime
from typing import List, Literal

ENABLED_LOG_LEVELS: List[Literal["all", "info", "success", "warning", "error", "progressbar"]] | str = "all"

COLORS = {
    "info": "\033[36m",
    "success": "\033[32m",
    "warning": "\033[33m",
    "error": "\033[31m",
    "grey": "\033[90m",
    "header": "\033[95m",
    "reset": "\033[0m"
}

PREFIXES = {
    "info": "ℹ️  [INFO]\t",  # Синий информационный
    "success": "✅ [SUCCESS]\t",  # Зелёный успех
    "warning": "⚠️  [WARNING]\t",  # Жёлтое предупреждение
    "error": "❌ [ERROR]\t",  # Красная ошибка
    "header": "📌 [SECTION]\t"
}

def log(message, status: Literal["info", "success", "warning", "error", "header"] = "info", **kwargs):
    global ENABLED_LOG_LEVELS, COLORS, PREFIXES

    if (ENABLED_LOG_LEVELS != "all") and ("all" not in ENABLED_LOG_LEVELS):
        if status not in ENABLED_LOG_LEVELS:
            return

    time_now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    prefix = PREFIXES.get(status, "ℹ️ [INFO]")
    color = COLORS.get(status, "\033[36m")

    print(f"{color}{prefix} [{time_now}] {message}{COLORS['reset']}", **kwargs)


anim = ['\\ ', '| ', '/ ', '- ']
anim_index = 0
_last_line_length = 0
_finished = False

def reset_progress():
    global _finished, _last_line_length
    _finished = False
    _last_line_length = 0


def progress(op_code, cur_count, max_count=None, message=''):
    global anim_index, _last_line_length, _finished, ENABLED_LOG_LEVELS, COLORS

    if (ENABLED_LOG_LEVELS != "all") and ("all" not in ENABLED_LOG_LEVELS):
        if "progressbar" not in ENABLED_LOG_LEVELS:
            return

    filled_char = '■'
    empty_char = '■'
    filled_color = COLORS['info']
    empty_color = COLORS['grey']

    is_finished = max_count is not None and cur_count >= max_count

    if is_finished and _finished:
        return
    if is_finished:
        _finished = True

    if is_finished:
        prefix = '✅'
    else:
        prefix = anim[anim_index % len(anim)]
        anim_index += 1

    bar_length = 30
    if max_count:
        filled_length = int(bar_length * cur_count // max_count)
    else:
        filled_length = 0
    empty_length = bar_length - filled_length
    bar = f"{filled_color}{filled_char * filled_length}{empty_color}{empty_char * empty_length}{COLORS['reset']}"

    line = f"{prefix} {bar} {message}"
    line_padded = line.ljust(_last_line_length)
    _last_line_length = len(line)

    sys.stdout.write('\r' + line_padded)
    sys.stdout.flush()

    if is_finished:
        print()
        reset_progress()
