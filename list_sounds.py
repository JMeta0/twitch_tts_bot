import os
import logging
import sys
from platform import system


system = system()
if system == 'Windows':
    sox_path = r'sox'
    os.environ['PATH'] = sox_path + ';' + os.environ['PATH']
    import sox
else:
    import sox


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
    print('Loading sounds...')
    for filename in os.listdir(sounds_directory):
        if filename.endswith('.wav'):
            fullpath = f'{sounds_directory}/{filename}'

            # Check number of channels and sample rate
            if sox.file_info.channels(fullpath) == 1 & int(sox.file_info.sample_rate(fullpath) == 22050.0):
                sounds.append(f'[{filename[:-4]}]')
            else:
                log.error(f'File {fullpath} is not mono channel or has wrong samplerate.')


    log.info(f'Succesfully loaded all sounds - {len(sounds)} sounds')
    return sounds
