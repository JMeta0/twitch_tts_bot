Load those python scripts - sound_play.py, split_message.py

Text is text. Example: "Nagle wyczuwa bardzo mocny swąd i słyszy". This text is sent to TTS server and gets saved as a .wav file.
Numbers in square brackets gets changed to sound effect like [150] is a path to soundfile with effect.
Then a list of generated sentences and sound files are merged to one file called output.wav and are getting played.

If I'd want to add functionality to apply filters on merged and generated texts and sound effects using curly brackets. Would it be better to change split_message.py to analyze character by character and save things to objects in array or analyze it like it's done currently?


I'd like to mark sounds that needs an effect applied with curly brackets. Number between '{' and '}' should be saved to array that will hold list of effects that will be applied to text and sound effects between effect start - like {4} and {.}. Sounds may be applied between words.

Example text to process:
Nagle wyczuwa bardzo mocny swąd i słyszy {4}[349]{.}. Przyspiesza krok i idzie w kierunku zapachu. Radecki wie, że zepsuł sprawę i zaczyna płakać [139] [134] szybko go znajduje i wyważa drzwi [287]. {2}Spojrzał się na Radka jak go zobaczył w brązowej zbroi [302] {3} szybko zdejmuje okulary [122][113][347] i patrzy na Radka i czeka na reakcje.

