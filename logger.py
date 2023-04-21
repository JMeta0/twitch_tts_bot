import os
import sys
import time
import logging
import glob


def truncate_logs(logs_folder, max_files=10):
    log_files = glob.glob(f"{logs_folder}/*.log")
    if len(log_files) >= max_files:
        oldest_file = min(log_files, key=os.path.getctime)
        os.remove(oldest_file)


def setup_external_loggers(file_handler, debug_mode):
    loggers_to_configure = [
        "twitchAPI.twitch",
        "twitchAPI.eventsub",
        "twitchAPI.pubsub",
        "twitchAPI.chat",
        "twitchAPI.oauth",
    ]

    log_level = logging.DEBUG if debug_mode else logging.INFO
    formatter = logging.Formatter('%(asctime)s - %(filename)s:%(lineno)d - %(levelname)s - %(message)s')

    for logger_name in loggers_to_configure:
        external_logger = logging.getLogger(logger_name)
        external_logger.setLevel(log_level)

        # Add console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(log_level)
        console_handler.setFormatter(formatter)
        external_logger.addHandler(console_handler)

        # Add the shared file handler
        external_logger.addHandler(file_handler)


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

    truncate_logs(logs_folder)

    start_time = time.strftime("%Y-%m-%d_%H-%M-%S")
    filename = os.path.join(logs_folder, f"logs_{start_time}.log")
    file_handler = logging.FileHandler(filename, encoding='utf-8')
    file_handler.setLevel(log_level)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    setup_external_loggers(file_handler, debug_mode)

    return logger


debug_mode = 'debug'.lower() in sys.argv
logger = setup_logging(debug_mode)
