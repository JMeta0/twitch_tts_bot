import os
import glob

# Set the directory where the .wav files are located
dir_path = 'tmp'


def clean_tmp():
    # Get a list of all .wav files in the directory
    wav_files = glob.glob(os.path.join(dir_path, '*.wav'))

    # Delete each .wav file
    for file in wav_files:
        os.remove(file)
