import sys
import logging
import logging.handlers
import time
from pathlib import Path
from typing import Optional

from dbus_service import RecommendSystemDbusService

FSS_ROOT = str(Path(__file__).resolve().parent.parent.parent)
if FSS_ROOT not in sys.path:
    sys.path.insert(0, FSS_ROOT)

NLP_MODEL_PATH = str(Path(__file__).resolve().parent.parent / "models" / "fss_ner_crf_optimized.joblib")
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

    log_file = log_path / "recommend_system_dbus.log"
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


def _lazy_load_nlp_engine():
    try:
        from RecipeAnalyzerAPI import RecipeAnalyzerEngine
        engine = RecipeAnalyzerEngine(
            model_path=NLP_MODEL_PATH,
            recipe_db_path=NLP_RECIPE_DB_PATH
        )
        logging.getLogger("RecommendSystemMain").info(
            "NLP engine loaded lazily on first recipe analysis"
        )
        return engine
    except Exception as e:
        logging.getLogger("RecommendSystemMain").error(
            f"Failed to load NLP engine: {e}"
        )
        return None


class RecommendSystemMain:
    def __init__(self):
        self.is_running = False
        self._nlp_engine = None
        self._nlp_loaded = False
        self.dbus_service = RecommendSystemDbusService()
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.info("RecommendSystemMain initialized")

    def init_service(self) -> bool:
        try:
            self.logger.info("=" * 70)
            self.logger.info("Recommend System D-Bus Service initialization starting")
            self.logger.info("=" * 70)

            self.logger.info("Initializing D-Bus service...")
            if not self.dbus_service.setup_bus_service():
                self.logger.error("Failed to setup D-Bus service")
                return False
            self.logger.info("D-Bus service initialized")

            self.logger.info("NLP engine will be loaded lazily on first request")
            self.logger.info("=" * 70)
            self.logger.info("Recommend System D-Bus Service initialization completed")
            self.logger.info("=" * 70)
            return True

        except Exception as e:
            self.logger.error(
                f"Unexpected error during initialization: {e}", exc_info=True
            )
            return False

    def start_service(self) -> bool:
        if self.is_running:
            self.logger.warning("Service already running")
            return True
        try:
            self.is_running = True
            if self.dbus_service:
                self.dbus_service.poll_bus_events()
            self.logger.info("Recommend System D-Bus Service started")
            return True
        except Exception as e:
            self.logger.error(f"Failed to start service: {e}")
            self.is_running = False
            return False

    def stop_service(self) -> None:
        self.logger.info("=" * 70)
        self.logger.info("Recommend System D-Bus Service stopping")
        self.logger.info("=" * 70)
        try:
            self.is_running = False
            if self.dbus_service:
                self.dbus_service.stop()
            self.logger.info("Recommend System D-Bus Service stopped successfully")
        except Exception as e:
            self.logger.error(f"Error during shutdown: {e}")

    def _ensure_nlp_engine(self) -> bool:
        if not self._nlp_loaded:
            self._nlp_engine = _lazy_load_nlp_engine()
            self._nlp_loaded = True
            if self._nlp_engine:
                self.dbus_service.set_nlp_engine(self._nlp_engine)
        return self._nlp_engine is not None


def main() -> int:
    setup_logging()
    logger = logging.getLogger("RecommendSystemMain")

    logger.info("=" * 80)
    logger.info("FSS Recommend System D-Bus Service Starting")
    logger.info("=" * 80)

    service = None

    try:
        service = RecommendSystemMain()
        if not service.init_service():
            logger.error("Failed to initialize service")
            return 1
        if not service.start_service():
            logger.error("Failed to start service")
            return 1
        logger.info("Recommend System D-Bus Service is running. Press Ctrl+C to stop.")
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
        logger.info("FSS Recommend System D-Bus Service Stopped")
        logger.info("=" * 80)


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
