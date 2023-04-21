# BezioBot for Twitch.tv - self hosted TTS solution with self created voice model.
To create voice model I used https://github.com/coqui-ai/TTS using VITS tts model.

- python 3.10

- Requires SoX to exist in sox directory or in PATH

- Requires TTS Server 0.13.3 running on http://localhost:5002

- Optionally you can put sounds in .wav format to `sounds` directory. They will be played using pattern like this `[150]` sound named `150.wav` will be played