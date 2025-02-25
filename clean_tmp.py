import os
import glob
from logger import logger

# Set the directory where the .wav files are located
TMP_DIR = 'tmp'


def clean_tmp():
    """
    Remove all .wav files from the temporary directory.
    
    This function is used to clean up temporary audio files after they've been processed.
    """
    logger.debug("Cleaning temporary files...")
    
    # Ensure the directory exists
    if not os.path.exists(TMP_DIR):
        try:
            os.makedirs(TMP_DIR)
            logger.info(f"Created temporary directory: {TMP_DIR}")
            return  # No files to clean in a new directory
        except Exception as e:
            logger.error(f"Failed to create temporary directory: {e}")
            return

    # Get a list of all .wav files in the directory
    try:
        wav_files = glob.glob(os.path.join(TMP_DIR, '*.wav'))
        logger.debug(f"Found {len(wav_files)} temporary files to clean")
        
        # Delete each .wav file
        deleted_count = 0
        for file in wav_files:
            try:
                os.remove(file)
                deleted_count += 1
            except Exception as e:
                logger.error(f"Failed to delete file {file}: {e}")
        
        logger.debug(f"Cleaned {deleted_count} temporary files")
    except Exception as e:
        logger.error(f'Clean Error: {e}')
