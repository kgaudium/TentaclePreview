import enum
import json
import sys
from datetime import datetime
from typing import List, Literal, Callable, Any, Dict


class LogType(enum.Enum):
    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"
    HEADER = "header"

class LogEntry:
    def __init__(self, message: str, log_type: LogType) -> None:
        if not isinstance(log_type, LogType):
            raise TypeError("type must be of type LogType")

        if not isinstance(message, str):
            raise TypeError("message must be of type str")

        self.message = message

        self.message = message
        self.log_type = log_type
        self.time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def __json__(self):
        return {
            "message": self.message,
            "log_type": self.log_type.value,
            "time": self.time
        }

ENABLED_LOG_LEVELS: List[Literal["all", "info", "success", "warning", "error", "progressbar"]] | str = "all"

on_log_event: List[Callable[[LogEntry, dict[str, Any]], None]] = []

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

def log(message: str, log_type: LogType | Literal["info", "success", "warning", "error", "header"] = LogType.INFO, **kwargs: Any) -> None:
    global ENABLED_LOG_LEVELS, COLORS, PREFIXES

    if isinstance(log_type, str):
        log_type = LogType(log_type)

    if (ENABLED_LOG_LEVELS != "all") and ("all" not in ENABLED_LOG_LEVELS):
        if log_type.value not in ENABLED_LOG_LEVELS:
            return

    log_entry = LogEntry(message, log_type)

    prefix = PREFIXES.get(log_type.value, "ℹ️ [INFO]")
    color = COLORS.get(log_type.value, "\033[36m")

    for event in on_log_event:
        event(log_entry, **kwargs)

    print(f"{color}{prefix} [{log_entry.time}] {message}{COLORS['reset']}", **kwargs)


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
