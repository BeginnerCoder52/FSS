import sys
import logging
import logging.handlers
import time
from pathlib import Path
from typing import Optional

from recipe_extractor_service import RecipeExtractorDbusService

FSS_ROOT = str(Path(__file__).resolve().parent.parent.parent)
if FSS_ROOT not in sys.path:
    sys.path.insert(0, FSS_ROOT)

NLP_RECIPE_DB_PATH = str(Path(__file__).resolve().parent.parent / "data" / "recipes")


def setup_logging(log_dir: str = "/var/log/fss") -> None:
    log_path = Path(log_dir)
    try:
        log_path.mkdir(parents=True, exist_ok=True)
    except (PermissionError, OSError):
        log_path = Path(__file__).parent.parent / "logs"
        log_path.mkdir(parents=True, exist_ok=True)
        print(f"WARNING: Cannot write to {log_dir}, falling back to {log_path}")

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)

    log_format = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - [%(threadName)s] - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(log_format)
    root_logger.addHandler(console_handler)

    log_file = log_path / "recipe_extractor.log"
    try:
        file_handler = logging.handlers.RotatingFileHandler(
            str(log_file),
            maxBytes=10 * 1024 * 1024,
            backupCount=5
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(log_format)
        root_logger.addHandler(file_handler)
    except (PermissionError, OSError):
        print(f"WARNING: Cannot create log file at {log_file}. "
              f"File logging disabled.")


class RecipeExtractorMain:
    def __init__(self):
        self.is_running = False
        self._nlp_engine = None
        self.dbus_service = RecipeExtractorDbusService()
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.info("RecipeExtractorMain initialized")

    def init_service(self) -> bool:
        try:
            self.logger.info("=" * 70)
            self.logger.info("Recipe Extractor D-Bus Service initialization starting")
            self.logger.info("=" * 70)

            self.logger.info("Loading recipe database...")
            self._nlp_engine = self._load_engine()
            if not self._nlp_engine:
                self.logger.error("Failed to load recipe database")
                return False
            self.dbus_service.set_nlp_engine(self._nlp_engine)
            self.logger.info(f"Recipe database loaded with {len(self._nlp_engine.recipe_names)} recipes")

            self.logger.info("Initializing D-Bus service...")
            if not self.dbus_service.setup_bus_service():
                self.logger.error("Failed to setup D-Bus service")
                return False
            self.logger.info("D-Bus service initialized")

            self.logger.info("=" * 70)
            self.logger.info("Recipe Extractor D-Bus Service initialization completed")
            self.logger.info("=" * 70)
            return True

        except Exception as e:
            self.logger.error(
                f"Unexpected error during initialization: {e}", exc_info=True
            )
            return False

    def _load_engine(self):
        try:
            from RecipeAnalyzerAPI import RecipeAnalyzerEngine
            engine = RecipeAnalyzerEngine(
                recipe_db_path=NLP_RECIPE_DB_PATH
            )
            self.logger.info("Recipe database engine loaded successfully")
            return engine
        except Exception as e:
            self.logger.error(f"Failed to load recipe database: {e}")
            return None

    def start_service(self) -> bool:
        if self.is_running:
            self.logger.warning("Service already running")
            return True
        try:
            self.is_running = True
            if self.dbus_service:
                self.dbus_service.poll_bus_events()
            self.logger.info("Recipe Extractor D-Bus Service started")
            return True
        except Exception as e:
            self.logger.error(f"Failed to start service: {e}")
            self.is_running = False
            return False

    def stop_service(self) -> None:
        self.logger.info("=" * 70)
        self.logger.info("Recipe Extractor D-Bus Service stopping")
        self.logger.info("=" * 70)
        try:
            self.is_running = False
            if self.dbus_service:
                self.dbus_service.stop()
            self.logger.info("Recipe Extractor D-Bus Service stopped successfully")
        except Exception as e:
            self.logger.error(f"Error during shutdown: {e}")

    def get_nlp_engine(self):
        return self._nlp_engine


def main() -> int:
    setup_logging()
    logger = logging.getLogger("RecipeExtractorMain")

    logger.info("=" * 80)
    logger.info("FSS Recipe Extractor D-Bus Service Starting")
    logger.info("=" * 80)

    service = None

    try:
        service = RecipeExtractorMain()
        if not service.init_service():
            logger.error("Failed to initialize service")
            return 1
        if not service.start_service():
            logger.error("Failed to start service")
            return 1
        logger.info("Recipe Extractor D-Bus Service is running. Press Ctrl+C to stop.")
        while service.is_running:
            try:
                time.sleep(1)
            except KeyboardInterrupt:
                logger.info("Received keyboard interrupt, shutting down...")
                break
        return 0
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
        return 0
    except Exception as e:
        logger.error(f"Unexpected error in main: {e}", exc_info=True)
        return 1
    finally:
        if service:
            service.stop_service()
        logger.info("=" * 80)
        logger.info("FSS Recipe Extractor D-Bus Service Stopped")
        logger.info("=" * 80)


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
