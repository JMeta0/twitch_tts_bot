import os
from logger import logger
from platform import system


system = system()
if system == 'Windows':
    sox_path = r'sox'
    os.environ['PATH'] = sox_path + ';' + os.environ['PATH']
    import sox
else:
    import sox


def list_sounds():
    sounds = []
    sounds_directory = "sounds"
    logger.info('Loading sounds...')
    
    # Check if sounds directory exists
    if not os.path.exists(sounds_directory):
        logger.warning(f'Sounds directory {sounds_directory} does not exist. Creating it.')
        os.makedirs(sounds_directory)
        
    try:
        for filename in os.listdir(sounds_directory):
            if filename.endswith('.wav'):
                fullpath = f'{sounds_directory}/{filename}'

                try:
                    # Check number of channels and sample rate
                    if sox.file_info.channels(fullpath) == 1 and sox.file_info.sample_rate(fullpath) == 22050.0:
                        sounds.append(f'[{filename[:-4]}]')
                    else:
                        logger.error(f'File {fullpath} is not mono channel or has wrong samplerate.')
                except Exception as e:
                    logger.error(f'Error analyzing sound file {fullpath}: {e}')
    except Exception as e:
        logger.error(f'Error listing sounds directory: {e}')

    logger.info(f'Successfully loaded all sounds - {len(sounds)} sounds')
    return sounds
