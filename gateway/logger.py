import sys
import json
import logging
from datetime import datetime, timezone


class JSONFormatter(logging.Formatter):
    # Formatter logów w formacie JSON (przydatne do agregacji w ELK / Loki / observability)
    def format(self, record):
        log_object = {
            # Timestamp w UTC – standard dla systemów rozproszonych
            "timestamp": datetime.now(timezone.utc).isoformat(),

            # Poziom logowania (INFO / ERROR / DEBUG itd.)
            "level": record.levelname,

            # Główna treść logu
            "message": record.getMessage(),

            # Źródło logu (moduł w kodzie)
            "module": record.module,

            # PID procesu (przydatne przy debugowaniu wielu workerów)
            "process": record.process
        }

        # Dodanie stack trace w przypadku wyjątków
        if record.exc_info:
            log_object["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_object)


def get_logger(name: str) -> logging.Logger:
    # Fabryka loggerów – zapewnia spójny format logowania w całej aplikacji
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    # Uniknięcie duplikacji handlerów przy wielokrotnym imporcie
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)

        # Ustawienie JSON formattera dla strukturalnych logów
        handler.setFormatter(JSONFormatter())

        logger.addHandler(handler)

    return logger