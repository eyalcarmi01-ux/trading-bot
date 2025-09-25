import logging
import os
from datetime import datetime

def setup_logger():
    logger = logging.getLogger('bot')
    logger.setLevel(logging.DEBUG)

    # ניקוי הנדלרים הקיימים כדי למנוע כפילויות
    if logger.hasHandlers():
        logger.handlers.clear()

    os.makedirs('logs', exist_ok=True)
    today_str = datetime.now().strftime('%Y-%m-%d')
    log_filename = f'logs/trading_{today_str}.log'

    formatter = logging.Formatter('%(asctime)s | %(levelname)s | %(message)s')

    file_handler = logging.FileHandler(log_filename, encoding='utf-8')
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.DEBUG)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.INFO)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    # Add visual padding at startup (10 empty lines) to both console and file outputs,
    # guarded so it only happens once per process.
    if not getattr(logger, '_padded', False):
        for h in (file_handler, console_handler):
            try:
                if hasattr(h, 'stream') and h.stream:
                    h.stream.write('\n' * 10)
                    h.flush()
            except Exception:
                # Best-effort padding; ignore any stream/IO issues
                pass
        setattr(logger, '_padded', True)

    return logger

# הגדרה אחת בלבד לכל הפרויקט
logger = setup_logger()