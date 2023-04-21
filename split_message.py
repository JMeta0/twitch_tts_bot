import re


async def split_message(text):
    # Split the string into individual tokens (words, square brackets, curly brackets)
    tokens = re.findall(r'\[[^\]]*\]|\{[^\}]*\}|[^\[\]\{\} ]+', text)

    # Merge non-bracketed and non-curly-bracketed words that appear next to each other
    merged_tokens = []
    for token in tokens:
        if merged_tokens and not re.match(r'(\[.*\]|\{.*\})', token) and not re.match(r'(\[.*|\{.*)', merged_tokens[-1]):
            merged_tokens[-1] += ' ' + token
        else:
            merged_tokens.append(token)

    return merged_tokens
