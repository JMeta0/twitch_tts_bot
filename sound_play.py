import sys
import os
import asyncio
import logging
import re
from clean_tmp import clean_tmp
from fix_numbers import fix_numbers
from platform import system
from simpleSound import play
from split_message import split_message
import urllib
import shutil
from parsed_config import parsed_config


# Meme config
cfg = parsed_config()
SOUND_CAP = cfg.tts.sound_cap


# Logs
log = logging.getLogger()
if "debug".lower() in sys.argv:
    log_level = logging.DEBUG
elif "info".lower() in sys.argv:
    log_level = logging.INFO
else:
    log_level = logging.ERROR

logging.basicConfig(level=log_level, format="%(name)s - %(message)s", datefmt="%X")
system = system()

if system == 'Windows':
    sox_path = r'sox'
    os.environ['PATH'] = sox_path + ';' + os.environ['PATH']
    import sox


async def sound_play(sound_queue, sounds_list):
    while True:
        try:
            log.debug('sound_play - waiting for item in queue.')

            message = await asyncio.wait_for(sound_queue.get(), timeout=1)
            log.debug(f'sound_play - Executing "{message}" from queue. Queue size: {sound_queue.qsize()}')

            # Split message and potential sounds,
            sentence_array = split_message(message)
            log.debug(f"sound_play - sentence_array - {sentence_array}")
            wavs = []

            # Get TTS sentences generated
            sound_number = 1
            for index, sentence in enumerate(sentence_array):
                # Check if name.wav exists in pattern - like 150.wav in sounds folder
                if sentence_array[index] in sounds_list:
                    if sound_number <= SOUND_CAP:
                        log.debug("sound_play - Found sentence in sounds array")
                        wavs.append(f'sounds/{sentence[1:-1]}.wav')
                        sound_number += 1
                    else:
                        log.debug("sound_play - Capped sound numbers. Skipping")
                        continue

                # Check for filter pattern {numer of filter} eg. {1}
                # elif any(filter_dict['name'] == sentence_array[index] for filter_dict in filters_list):
                #     filter_value = next(filter_dict['value'] for filter_dict in filters_list if filter_dict['name'] == sentence_array[index])
                #     log.debug(f'Filter pattern detected. Value: {filter_value}')
                #     wavs.append(sentence_array[index])
                # If it's normal sentence, send it to TTS server
                else:
                    sentence = fix_numbers(sentence)
                    if not bool(re.match(".*(\.|!|\?)$", sentence)):
                        sentence += "."

                    url = f"http://localhost:5002/api/tts?text={urllib.parse.quote_plus(sentence)}"
                    os.system(f'curl.exe -s {url} -o tmp/{index}.wav')
                    wavs.append(f'tmp/{index}.wav')

            # ADD {1} LOGIC HERE!
            log.debug(f"sound_play - files are {wavs}")

            combiner = sox.Combiner()

            if len(wavs) > 1:
                combiner.build(wavs, "output.wav", "concatenate")
            elif len(wavs) == 1:
                shutil.copy(wavs[0], "output.wav")

            # Play
            if system == 'Windows':
                log.debug(f'sound_play - Playing sound on {system}')
                play('./output.wav')
                os.remove('./output.wav')
            if system == 'Linux':
                log.debug(f'sound_play - Playing sound on {system}')
                os.system('aplay -q ./output.wav')
                os.remove('./output.wav')
            clean_tmp()
            # Remove item from queue
            sound_queue.task_done()
            log.debug(f'sound_play - Task done. Queue size: {sound_queue.qsize()}')
        except asyncio.TimeoutError:
            pass
