import logging
from logging.handlers import RotatingFileHandler

from app.config import get_app_settings

SECRET_MARKERS = ("secret", "webhook", "password", "token", "authorization")


class SecretRedactionFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        for marker in SECRET_MARKERS:
            if marker in message.lower():
                record.msg = "[redacted log message containing sensitive marker]"
                record.args = ()
                break
        return True


def setup_logging() -> None:
    settings = get_app_settings()
    formatter = logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s")

    file_handler = RotatingFileHandler(settings.log_path, maxBytes=1_000_000, backupCount=5)
    file_handler.setFormatter(formatter)
    file_handler.addFilter(SecretRedactionFilter())

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.addFilter(SecretRedactionFilter())

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.handlers.clear()
    root.addHandler(file_handler)
    root.addHandler(console_handler)
