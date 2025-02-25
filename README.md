# BezioBot for Twitch.tv - self hosted TTS solution with self created voice model.
To create voice model I used https://github.com/coqui-ai/TTS using VITS tts model.

- python 3.10

- Requires [SoX](https://sourceforge.net/projects/sox/) to exist in ./sox directory or in PATH

- Required [curl](https://curl.se/windows/) to exist in root directory or in PATH

- Requires TTS Server 0.13.3 running on http://localhost:5002

- Optionally you can put sounds in .wav format to `sounds` directory. They will be played using pattern like this `[150]` sound named `150.wav` will be played. Needs to be 22050hz, mono channel.


# Eventsub local testing
- Install [Twitch CLI](https://dev.twitch.tv/docs/)
- `twitch mock-api generate`
  - Grab User ID, Client-ID and Secret and put it in config
- `twitch mock-api start`
- `twitch event websocket start-server -p 4000`
- Install all requirements of twitch_tts_bot
- Start TTS server `tts-server --model_path best_model.pth --config_path config.json --use_cuda true`
- Trigger custom reward event `twitch event trigger channel.channel_points_custom_reward_redemption.add -T websocket -t <USER_ID> -u <SUBSCRIPTION_ID>`