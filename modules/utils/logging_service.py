from __future__ import annotations

import logging
from pathlib import Path


class ActionLogger:
    def __init__(self, directory: str) -> None:
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.logger = logging.getLogger("selfbot.actions")

    def info(self, module: str, action: str, target: str, result: str) -> None:
        self.logger.info("[%s] [%s] [%s] [%s]", module, action, target, result)

    def warning(self, module: str, action: str, target: str, result: str) -> None:
        self.logger.warning("[%s] [%s] [%s] [%s]", module, action, target, result)

    def error(self, module: str, action: str, target: str, result: str) -> None:
        self.logger.error("[%s] [%s] [%s] [%s]", module, action, target, result)
