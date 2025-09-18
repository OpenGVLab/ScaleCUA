import logging
from pathlib import Path
from typing import Optional

class ProjectLogger:
    def __init__(self, name: str = "evalkit_macos", log_dir: Optional[Path] = None):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.DEBUG)

        if not self.logger.handlers:
            formatter = logging.Formatter(
                "[%(asctime)s] [%(levelname)s] [%(filename)s:%(lineno)d] %(message)s",
                "%Y-%m-%d %H:%M:%S"
            )

            # Console output only
            console_handler = logging.StreamHandler()
            console_handler.setLevel(logging.INFO)
            console_handler.setFormatter(formatter)
            self.logger.addHandler(console_handler)

            # Optional file output
            if log_dir:
                log_dir.mkdir(parents=True, exist_ok=True)
                file_handler = logging.FileHandler(log_dir / f"{name}.log")
                file_handler.setLevel(logging.DEBUG)
                file_handler.setFormatter(formatter)
                self.logger.addHandler(file_handler)

    def info(self, msg): self.logger.info(msg, stacklevel=2)
    def debug(self, msg): self.logger.debug(msg, stacklevel=2)
    def warning(self, msg): self.logger.warning(msg, stacklevel=2)
    def error(self, msg): self.logger.error(msg, stacklevel=2)
    def critical(self, msg): self.logger.critical(msg, stacklevel=2)
    def get(self): return self.logger