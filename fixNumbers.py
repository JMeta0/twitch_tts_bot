from num2words import num2words

def fix_numbers(text):
    words = []
    for word in text.split():
        # Check if the word is a number
        if word.isnumeric():
            # Convert number to word and add to list of words
            words.append(num2words(int(word), lang='pl'))
        else:
            words.append(word)
    # Join list of words back into a string
    return ' '.join(words)
