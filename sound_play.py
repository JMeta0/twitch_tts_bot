import asyncio
import logging
import os
import re
import shutil
import urllib
import uuid
import subprocess
from clean_tmp import clean_tmp
from fix_numbers import fix_numbers
from logger import logger
from parsed_config import parsed_config
from platform import system
from simpleSound import play
from split_message import split_message
from collections import Counter


# System detection
SYSTEM = system()

# Configure sox and curl based on platform
if SYSTEM == 'Windows':
    sox_path = r'sox'
    os.environ['PATH'] = sox_path + ';' + os.environ['PATH']
    CURL_COMMAND = 'curl.exe'
    import sox
else:
    CURL_COMMAND = 'curl'
    import sox

logging.getLogger('sox').setLevel(logging.ERROR)


class SoundProcessor:
    """
    Handles sound processing and playback for TTS messages.
    """
    
    def __init__(self, sounds_list):
        """
        Initialize the sound processor.
        
        Args:
            sounds_list (list): List of available sound effects
        """
        # Load configuration
        cfg = parsed_config()
        self.sound_cap = cfg.tts.sound_cap
        self.max_effect_repetitions = cfg.tts.max_effect_repetitions
        self.sounds_list = sounds_list
        self.current_sound_cap = 0
        
        # Ensure tmp directory exists
        if not os.path.exists('tmp'):
            os.makedirs('tmp')

    async def sound_play_loop(self, sound_queue):
        """
        Main loop that processes messages from the queue.
        
        Args:
            sound_queue (asyncio.Queue): Queue containing messages to process
        """
        logger.debug('sound_play - waiting for item in queue.')
        while True:
            try:
                message = await asyncio.wait_for(sound_queue.get(), timeout=1)
                logger.debug(f'sound_play - Executing "{message}" from queue. Queue size: {sound_queue.qsize()}')

                try:
                    # Process and play the message
                    await self.process_message(message)
                except Exception as e:
                    logger.error(f'Error processing message: {e}')
                
                # Release the queue item
                sound_queue.task_done()
                logger.debug(f'sound_play - Task done. Queue size: {sound_queue.qsize()}')
                
            except asyncio.TimeoutError:
                # No new messages in queue, continue waiting
                pass
            except Exception as e:
                logger.error(f'Unexpected error in sound play loop: {e}')

    async def process_message(self, message):
        """
        Process a message into speech and sounds.
        
        Args:
            message (str): The message to process
        """
        # Reset sound cap for this message
        self.current_sound_cap = 0
        
        # Split message into tokens
        tokens = await split_message(message)
        logger.debug(f'sound_play - tokens - {tokens}')

        if not tokens:
            logger.warning("No tokens found in message")
            return

        wavs = []
        segment = []
        effect_ids = []

        for token in tokens:
            if re.match(r'\{\d+\}', token):
                if segment:
                    wavs.append(await self.process_segment(segment, effect_ids))
                    segment = []
                effect_ids.append(int(token[1:-1]))
            elif token == '{.}':
                if segment:
                    wavs.append(await self.process_segment(segment, effect_ids))
                    segment = []
                effect_ids = []
            else:
                segment.append(token)
                
        logger.debug(f'sound_play - processing last segment: {segment}')
        if segment:
            wavs.append(await self.process_segment(segment, effect_ids))
            logger.debug(f'sound_play - processed last segment, resulting wav: {wavs}')

        logger.debug(f'sound_play - files are {wavs}')

        await self.combine_and_play_wavs(wavs)

    async def process_segment(self, segment, effect_ids):
        """
        Process a segment of tokens into a single audio file.
        
        Args:
            segment (list): List of text/sound tokens
            effect_ids (list): List of effects to apply
            
        Returns:
            str: Path to the processed audio file
        """
        logger.debug(f'process_segment - segment: {segment}, effect_ids: {effect_ids}')

        input_files = []
        
        try:
            for text in segment:
                if text.startswith('[') and text.endswith(']') and text in self.sounds_list:
                    if self.current_sound_cap < self.sound_cap:
                        input_files.append(f'sounds/{text[1:-1]}.wav')
                        self.current_sound_cap += 1
                else:
                    try:
                        # Process text-to-speech
                        text = await fix_numbers(text)
                        if not bool(re.match(r'.*(\.|!|\?)$', text)):
                            text += '.'

                        url = f'http://localhost:5002/api/tts?text={urllib.parse.quote_plus(text)}'
                        temp_filename = f'tmp/{uuid.uuid4()}.wav'
                        
                        result = subprocess.run(
                            [CURL_COMMAND, '-s', url, '-o', temp_filename], 
                            capture_output=True, 
                            text=True
                        )
                        
                        if result.returncode == 0 and os.path.exists(temp_filename) and os.path.getsize(temp_filename) > 0:
                            input_files.append(temp_filename)
                        else:
                            logger.error(f'Error while making request to TTS server: {result.stderr}')
                    except Exception as e:
                        logger.error(f'Error processing text: {e}')

            logger.debug(f'process_segment - input_files: {input_files}')
            
            if not input_files:
                logger.warning("No input files generated for segment")
                return None
                
            output_file = f'tmp/{uuid.uuid4()}.wav'
            await self.apply_effect(effect_ids, input_files, output_file)

            # Clean up temporary input files
            for input_file in input_files:
                if not input_file.startswith('sounds/') and os.path.exists(input_file):
                    try:
                        os.remove(input_file)
                    except Exception as e:
                        logger.error(f'Error removing temporary file {input_file}: {e}')

            return output_file
            
        except Exception as e:
            logger.error(f'Error in process_segment: {e}')
            return None

    async def apply_effect(self, effect_ids, input_files, output_file):
        """
        Apply audio effects to the input files.
        
        Args:
            effect_ids (list): List of effect IDs to apply
            input_files (list): List of input audio files
            output_file (str): Path to the output file
        """
        try:
            tfm = sox.Transformer()
            
            # Skip if no input files
            if not input_files:
                logger.warning("No input files to apply effects to")
                return
                
            # Concatenate input files
            combined_input = 'tmp/combined_input.wav'
            
            combiner = sox.Combiner()
            if len(input_files) > 1:
                combiner.build(input_files, combined_input, 'concatenate')
            elif len(input_files) == 1:
                shutil.copy(input_files[0], combined_input)
            else:
                logger.warning("No input files to combine")
                return

            # Limit effect repetitions based on configuration
            effect_counts = Counter(effect_ids)
            if self.max_effect_repetitions is not None:
                for effect_id, count in effect_counts.items():
                    if count > self.max_effect_repetitions:
                        effect_counts[effect_id] = self.max_effect_repetitions

            # Apply effects
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
                        logger.warning(f"Unknown effect ID: {effect_id}")

            # Build the final output
            tfm.build(combined_input, output_file)
            
            # Clean up the combined input file
            if os.path.exists(combined_input):
                os.remove(combined_input)
                
        except Exception as e:
            logger.error(f'Error applying effects: {e}')

    async def combine_and_play_wavs(self, wavs):
        """
        Combine multiple WAV files and play the result.
        
        Args:
            wavs (list): List of WAV file paths to combine and play
        """
        try:
            # Skip if no WAV files
            if not wavs or all(w is None for w in wavs):
                logger.warning("No valid WAV files to play")
                return
                
            # Remove None entries
            wavs = [w for w in wavs if w is not None]
            
            output_file = 'output.wav'
            
            # Combine WAVs if there are multiple files
            if len(wavs) > 1:
                combiner = sox.Combiner()
                combiner.build(wavs, output_file, 'concatenate')
            elif len(wavs) == 1:
                shutil.copy(wavs[0], output_file)
            else:
                logger.warning("No WAV files to combine")
                return

            # Play the combined WAV
            task = asyncio.to_thread(self.play_audio, output_file)
            await asyncio.create_task(task)
            
            # Clean up temporary WAV files
            for wav in wavs:
                if os.path.exists(wav):
                    try:
                        os.remove(wav)
                    except Exception as e:
                        logger.error(f'Error removing temporary WAV file {wav}: {e}')
                        
        except Exception as e:
            logger.error(f'Error combining and playing WAVs: {e}')

    def play_audio(self, file_path):
        """
        Play an audio file.
        
        Args:
            file_path (str): Path to the audio file to play
        """
        try:
            if SYSTEM == 'Windows':
                logger.debug(f'Playing sound on {SYSTEM}')
                play(file_path)
            elif SYSTEM == 'Linux':
                logger.debug(f'Playing sound on {SYSTEM}')
                result = subprocess.run(['aplay', '-q', file_path], capture_output=True, text=True)
                if result.returncode != 0:
                    logger.error(f'Error playing sound on Linux: {result.stderr}')
            else:
                logger.error(f'Unsupported system: {SYSTEM}')
                
            # Clean up the played file
            if os.path.exists(file_path):
                os.remove(file_path)
                
            # Clean temporary files
            clean_tmp()
            
        except Exception as e:
            logger.error(f'Error playing audio: {e}')


async def sound_play(sound_queue, sounds_list):
    """
    Main entry point for sound processing.
    
    Args:
        sound_queue (asyncio.Queue): Queue containing messages to process
        sounds_list (list): List of available sound effects
    """
    processor = SoundProcessor(sounds_list)
    await processor.sound_play_loop(sound_queue)
