import logging
import sys
import time
import os


def setup_logging(debug_mode):
    logger = logging.getLogger(__name__)

    if debug_mode:
        logger.setLevel(logging.DEBUG)
        log_level = logging.DEBUG
        formatter = logging.Formatter('%(asctime)s - %(filename)s:%(lineno)d - %(levelname)s - %(message)s')
    else:
        logger.setLevel(logging.INFO)
        log_level = logging.INFO
        formatter = logging.Formatter('%(message)s')

    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    logs_folder = os.path.join(os.getcwd(), 'logs')
    if not os.path.exists(logs_folder):
        os.makedirs(logs_folder)

    start_time = time.strftime("%Y-%m-%d_%H-%M-%S")
    filename = os.path.join(logs_folder, f"logs_{start_time}.log")
    file_handler = logging.FileHandler(filename)
    file_handler.setLevel(log_level)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger


debug_mode = 'debug'.lower() in sys.argv
logger = setup_logging(debug_mode)
