import asyncio
import logging
import os
import re
import shutil
import urllib
import uuid
from clean_tmp import clean_tmp
from fix_numbers import fix_numbers
from logger import logger
from parsed_config import parsed_config
from platform import system
from simpleSound import play
from split_message import split_message
from collections import Counter


# Meme config
cfg = parsed_config()
SOUND_CAP = cfg.tts.sound_cap
MAX_EFFECT_REPETITIONS = cfg.tts.max_effect_repetitions

system = system()

if system == 'Windows':
    sox_path = r'sox'
    os.environ['PATH'] = sox_path + ';' + os.environ['PATH']
    curl_command = 'curl.exe'
    import sox
else:
    curl_command = 'curl'
    import sox

logging.getLogger('sox').setLevel(logging.ERROR)


async def sound_play(sound_queue, sounds_list):
    logger.debug('sound_play - waiting for item in queue.')
    while True:
        try:
            message = await asyncio.wait_for(sound_queue.get(), timeout=1)
            logger.debug(f'sound_play - Executing "{message}" from queue. Queue size: {sound_queue.qsize()}')

            # Split message and potential sounds,
            tokens = await split_message(message)
            logger.debug(f'sound_play - tokens - {tokens}')

            wavs = []
            segment = []
            effect_ids = []

            for token in tokens:
                if re.match(r'\{\d+\}', token):
                    if segment:
                        wavs.append(await process_segment(segment, effect_ids, sounds_list))
                        segment = []
                    effect_ids.append(int(token[1:-1]))
                elif token == '{.}':

                    if segment:
                        wavs.append(await process_segment(segment, effect_ids, sounds_list))
                        segment = []
                    effect_ids = []
                else:
                    segment.append(token)
            logger.debug(f'sound_play - processing last segment: {segment}')
            if segment:
                wavs.append(await process_segment(segment, effect_ids, sounds_list))
                logger.debug(f'sound_play - processed last segment, resulting wav: {wavs}')

            logger.debug(f'sound_play - files are {wavs}')

            combiner = sox.Combiner()

            if len(wavs) != 0:
                # Play
                if len(wavs) > 1:
                    combiner.build(wavs, 'output.wav', 'concatenate')
                elif len(wavs) == 1:
                    shutil.copy(wavs[0], 'output.wav')

                task = asyncio.to_thread(async_play, 'output.wav')
                await asyncio.create_task(task)

            # Remove item from queue
            sound_queue.task_done()
            logger.debug(f'sound_play - Task done. Queue size: {sound_queue.qsize()}')
        except asyncio.TimeoutError:
            pass
        except Exception as e:
            logger.error(f'Error: {e}')


async def process_segment(segment, effect_ids, sounds_list):
    logger.debug(f'process_segment - segment: {segment}, effect_ids: {effect_ids}')

    input_files = []
    for index, text in enumerate(segment):
        if text.startswith('[') and text.endswith(']') and text in sounds_list:
            input_files.append(f'sounds/{text[1:-1]}.wav')
        else:
            text = await fix_numbers(text)
            if not bool(re.match('.*(\.|!|\?)$', text)):
                text += '.'

            url = f'http://localhost:5002/api/tts?text={urllib.parse.quote_plus(text)}'
            temp_filename = f'tmp/{uuid.uuid4()}.wav'
            os.system(f'{curl_command} -s {url} -o {temp_filename}')
            input_files.append(temp_filename)

    logger.debug(f'process_segment - input_files: {input_files}')
    output_file = f'tmp/{uuid.uuid4()}.wav'
    await apply_effect(effect_ids, input_files, output_file)

    sounds_dir = 'sounds'
    # Clean up temporary input files
    for input_file in input_files:
        if not os.path.commonprefix([sounds_dir, input_file]) == sounds_dir:
            os.remove(input_file)

    return output_file


async def apply_effect(effect_ids, input_files, output_file):
    tfm = sox.Transformer()

    # Concatenate input files
    combiner = sox.Combiner()

    if len(input_files) > 1:
        combiner.build(input_files, 'tmp/combined_input.wav', 'concatenate')
    elif len(input_files) == 1:
        shutil.copy(input_files[0], 'tmp/combined_input.wav')

    effect_counts = Counter(effect_ids)
    if MAX_EFFECT_REPETITIONS is not None:
        for effect_id, count in effect_counts.items():
            if count > MAX_EFFECT_REPETITIONS:
                effect_counts[effect_id] = MAX_EFFECT_REPETITIONS

    for effect_id, count in effect_counts.items():
        for _ in range(count):
            if effect_id == 1:
                # room echo
                tfm.reverb(50, room_scale=25)
            elif effect_id == 2:
                # hall echo
                tfm.reverb(75, room_scale=75, wet_gain=1)
            elif effect_id == 3:
                # outside echo
                tfm.reverb(5, room_scale=5)
            elif effect_id == 4:
                # pitch down
                tfm.pitch(-5)  # half an octave
            elif effect_id == 5:
                # pitch up
                tfm.pitch(5)  # half an octave
            elif effect_id == 6:
                # telephone
                tfm.highpass(800).gain(2)
            elif effect_id == 7:
                # muffled
                tfm.lowpass(1200).gain(1)
            elif effect_id == 8:
                # quieter
                tfm.gain(-20)
            elif effect_id == 9:
                # ghost
                (tfm
                    .pad(0.5, 0.5)
                    .reverse()
                    .reverb(reverberance=50, wet_gain=1)
                    .reverse()
                    .reverb())
            elif effect_id == 10:
                # chorus
                tfm.chorus()
            elif effect_id == 11:
                # slow down
                tfm.tempo(0.5)
            elif effect_id == 12:
                # speed up
                tfm.tempo(1.5)
            else:
                continue

    tfm.build('tmp/combined_input.wav', output_file)


def async_play(file_path):
    if system == 'Windows':
        logger.debug(f'sound_play - Playing sound on {system}')
        play(file_path)
        os.remove(file_path)
    elif system == 'Linux':
        logger.debug(f'sound_play - Playing sound on {system}')
        os.system('aplay -q ' + file_path)
        os.remove(file_path)
    clean_tmp()
