import logging
import sys

def setup_logger() -> logging.Logger:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        stream=sys.stdout,
    )
    return logging.getLogger("fps_coach_clean_smart_v2")