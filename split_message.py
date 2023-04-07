import re


def split_message(text):

    # Split the string into individual words
    words = re.findall(r'\[[^\]]*\]|[^\[\] ]+', text)

    # Merge non-bracketed words that appear next to each other
    merged_words = []
    for word in words:
        if merged_words and not re.match(r'\[.*\]', word) and not re.match(r'\[.*', merged_words[-1]):
            merged_words[-1] += ' ' + word
        else:
            merged_words.append(word)

    # Print the resulting array
    return merged_words