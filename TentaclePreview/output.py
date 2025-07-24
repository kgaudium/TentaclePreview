from datetime import datetime


def log(message, status="info"):
    """Улучшенное логирование с цветами, временем и тематическими префиксами."""
    time_now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    prefixes = {
        "info": "ℹ️ [INFO]",  # Синий информационный
        "success": "✅ [SUCCESS]",  # Зелёный успех
        "warning": "⚠️ [WARNING]",  # Жёлтое предупреждение
        "error": "❌ [ERROR]"  # Красная ошибка
    }

    colors = {
        "info": "\033[36m",  # Голубой
        "success": "\033[32m",  # Зелёный
        "warning": "\033[33m",  # Жёлтый
        "error": "\033[31m",  # Красный
        "reset": "\033[0m"  # Сброс цвета
    }

    prefix = prefixes.get(status, "ℹ️ [INFO]")
    color = colors.get(status, "\033[36m")

    print(f"{color}{prefix} [{time_now}] {message}{colors['reset']}")