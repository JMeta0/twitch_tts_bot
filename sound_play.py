import asyncio
import logging
import os
import re
import sys
from clean_tmp import clean_tmp
from fix_numbers import fix_numbers
from platform import system
from pydub import AudioSegment
from simpleSound import play
from split_message import split_message
import urllib

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


async def sound_play(sound_queue, sounds_list):
    while True:
        try:
            log.debug('sound_play - waiting for item in queue.')

            message = await asyncio.wait_for(sound_queue.get(), timeout=1)
            log.debug(f'sound_play - Executing {message} from queue. Queue size: {sound_queue.qsize()}')

            # Split message and potential sounds,
            sentence_array = split_message(message)
            log.debug(f"sentence_array - {sentence_array}")
            wavs = []
            log.debug(f"working on sentences - {sentence_array}")

            for index, sentence in enumerate(sentence_array):
                if sentence_array[index] in sounds_list:
                    log.debug("found sentence in sounds array")
                    wavs.append(f'sounds/{sentence[1:-1]}.wav')
                else:
                    # Fix numbers
                    sentence = fix_numbers(sentence)
                    # Add symbol at message end if it doesn't exist
                    if not bool(re.match(".*(\.|!|\?)$", sentence)):
                        sentence += "."

                    log.debug(sentence)

                    url = f"http://localhost:5002/api/tts?text={urllib.parse.quote_plus(sentence)}"
                    os.system(f'curl.exe -s {url} -o tmp/{index}.wav')

                    wavs.append(f'tmp/{index}.wav')
            log.debug(f"sound_play - files are {wavs}")

            combined_sounds = AudioSegment.empty()
            log.debug("sound_play - combining output")
            for path in wavs:
                combined_sounds += AudioSegment.from_wav(path)
            log.debug("sound_play - exporting output")
            combined_sounds.export("output.wav", format="wav")

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
