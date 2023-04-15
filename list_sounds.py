from os import listdir
import logging
import sys

# Logs
log = logging.getLogger()
if "debug".lower() in sys.argv:
    log_level = logging.DEBUG
elif "info".lower() in sys.argv:
    log_level = logging.INFO
else:
    log_level = logging.ERROR

logging.basicConfig(level=log_level, format="%(name)s - %(message)s", datefmt="%X")


def list_sounds():
    sounds = []
    sounds_directory = "sounds"

    for filename in listdir(sounds_directory):
        if filename.endswith('.wav'):
            sounds.append(f'[{filename[:-4]}]')
    log.info(f'Succesfully loaded all sounds - {len(sounds)} sounds')
    return sounds
