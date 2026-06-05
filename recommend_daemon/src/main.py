import sys
import logging
import logging.handlers
import json
import os
import signal
import time
from pathlib import Path
from typing import Optional

from RecommendEngine import RecommendEngine
from DbusInterface import RecommendDbusInterface
from RecommendDbManager import RecommendDbManager

FSS_ROOT = str(Path(__file__).resolve().parent.parent.parent)
if FSS_ROOT not in sys.path:
    sys.path.insert(0, FSS_ROOT)

NLP_MODEL_PATH = os.path.join(FSS_ROOT, "recipe_extractor", "models",
                              "fss_ner_crf_optimized.joblib")
NLP_RECIPE_DB_PATH = os.path.join(FSS_ROOT, "recipe_extractor", "data", "recipes")
DB_DIR = "/opt/fss/data"


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

    log_file = log_path / "recommend_daemon.log"
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
        from recipe_extractor.src.RecipeAnalyzerAPI import RecipeAnalyzerEngine
        engine = RecipeAnalyzerEngine(
            model_path=NLP_MODEL_PATH,
            recipe_db_path=NLP_RECIPE_DB_PATH
        )
        logging.getLogger("RecommendDaemonMain").info(
            "NLP engine loaded lazily on first recipe analysis"
        )
        return engine
    except Exception as e:
        logging.getLogger("RecommendDaemonMain").error(
            f"Failed to load NLP engine: {e}"
        )
        return None


class RecommendDaemonMain:
    def __init__(self):
        self.is_running = False
        self._nlp_engine = None
        self._nlp_loaded = False

        self.engine = RecommendEngine()
        self.db_manager = RecommendDbManager(db_dir=DB_DIR)
        self.dbus_interface = RecommendDbusInterface()

        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.info("RecommendDaemonMain initialized")

        signal.signal(signal.SIGTERM, self._handle_signal)
        signal.signal(signal.SIGINT, self._handle_signal)

    def init_daemon(self) -> bool:
        try:
            self.logger.info("=" * 70)
            self.logger.info("RecommendDaemon initialization starting")
            self.logger.info("=" * 70)

            self.logger.info("Initializing database manager...")
            if not self.db_manager.connect_db():
                self.logger.error("Failed to connect to FSS-Recommend database")
                return False
            self.db_manager.init_tables()
            self.engine.set_db_manager(self.db_manager)
            self.logger.info("Database manager initialized")

            self.logger.info("Initializing D-Bus interface...")
            if not self.dbus_interface.setup_bus_service():
                self.logger.error("Failed to setup D-Bus service")
                return False

            self.dbus_interface.set_generate_callback(
                self._handle_generate_shopping_list
            )
            self.dbus_interface.set_recipes_callback(
                self._handle_get_available_recipes
            )
            self.dbus_interface.set_shopping_list_callback(
                self._handle_get_shopping_list
            )
            self.dbus_interface.set_mark_purchased_callback(
                self._handle_mark_item_purchased
            )
            self.logger.info("D-Bus interface initialized")

            self.logger.info("NLP engine will be loaded lazily on first request")
            self.logger.info("=" * 70)
            self.logger.info("RecommendDaemon initialization completed")
            self.logger.info("=" * 70)
            return True

        except Exception as e:
            self.logger.error(
                f"Unexpected error during initialization: {e}", exc_info=True
            )
            return False

    def start_daemon(self) -> bool:
        if self.is_running:
            self.logger.warning("Daemon already running")
            return True
        try:
            self.is_running = True
            if self.dbus_interface:
                self.dbus_interface.poll_bus_events()
            self.logger.info("RecommendDaemon started")
            return True
        except Exception as e:
            self.logger.error(f"Failed to start daemon: {e}")
            self.is_running = False
            return False

    def stop_daemon(self) -> None:
        self.logger.info("=" * 70)
        self.logger.info("RecommendDaemon stopping")
        self.logger.info("=" * 70)
        try:
            self.is_running = False
            if self.dbus_interface:
                self.dbus_interface.stop()
            if self.db_manager:
                self.db_manager.close_connection()
            self.logger.info("RecommendDaemon stopped successfully")
        except Exception as e:
            self.logger.error(f"Error during shutdown: {e}")

    def _ensure_nlp_engine(self) -> bool:
        if not self._nlp_loaded:
            self._nlp_engine = _lazy_load_nlp_engine()
            self._nlp_loaded = True
            if self._nlp_engine:
                self.engine.set_nlp_engine(self._nlp_engine)
        return self._nlp_engine is not None

    def _get_inventory_from_dbd(self) -> list:
        try:
            result_json = self.dbus_interface.call_get_inventory()
            data = json.loads(result_json)
            if isinstance(data, list):
                return data
            if isinstance(data, dict) and "status" in data:
                if data.get("status") == "error":
                    self.logger.error(
                        f"DBDaemon GetInventory error: {data.get('message')}"
                    )
                return []
            return []
        except Exception as e:
            self.logger.error(f"Failed to get inventory from DBDaemon: {e}")
            return []

    def _handle_generate_shopping_list(
        self, recipe_name: str, batch_id: str
    ) -> dict:
        self.logger.info(
            f"GenerateShoppingList called: recipe='{recipe_name}', "
            f"batch_id='{batch_id}'"
        )
        if not self._ensure_nlp_engine():
            return {
                "status": "ERROR",
                "error": "NLP engine failed to initialize"
            }

        inventory = self._get_inventory_from_dbd()
        result = self.engine.generate_shopping_list(
            recipe_name=recipe_name,
            batch_id=batch_id,
            inventory=inventory
        )

        if result.get("status") == "SUCCESS":
            ui_result = self.engine.format_result_for_ui(result)

            if self.dbus_interface.is_connected:
                shopping_list_json = json.dumps(
                    ui_result.get("shopping_list", []), ensure_ascii=False
                )
                self.dbus_interface.emit_recommendation_updated(
                    recipe_name, shopping_list_json
                )

            return ui_result

        return result

    def _handle_get_available_recipes(self) -> list:
        self.logger.info("GetAvailableRecipes called")
        self._ensure_nlp_engine()
        return self.engine.get_available_recipes()

    def _handle_get_shopping_list(self, batch_id: str) -> list:
        self.logger.info(f"GetShoppingList called: batch_id='{batch_id}'")
        return self.engine.get_shopping_list(batch_id)

    def _handle_mark_item_purchased(self, item_id: int) -> bool:
        self.logger.info(f"MarkItemPurchased called: item_id={item_id}")
        return self.engine.mark_item_purchased(item_id)

    def _handle_signal(self, signum, frame) -> None:
        self.logger.info(
            f"Received signal {signum}, initiating graceful shutdown..."
        )
        self.stop_daemon()


def main() -> int:
    setup_logging()
    logger = logging.getLogger("RecommendDaemonMain")

    logger.info("=" * 80)
    logger.info("FSS Recommend Daemon Starting")
    logger.info("=" * 80)

    daemon = None

    try:
        daemon = RecommendDaemonMain()
        if not daemon.init_daemon():
            logger.error("Failed to initialize daemon")
            return 1
        if not daemon.start_daemon():
            logger.error("Failed to start daemon")
            return 1
        logger.info("RecommendDaemon is running. Press Ctrl+C to stop.")
        while daemon.is_running:
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
        if daemon:
            daemon.stop_daemon()
        logger.info("=" * 80)
        logger.info("FSS Recommend Daemon Stopped")
        logger.info("=" * 80)


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
