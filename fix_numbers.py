from num2words import num2words


def fix_numbers(text):
    symbols = []
    symbol_buffer = ''
    for symbol in text:
        if symbol.isnumeric():
            # Add numeric symbol to buffer because it might contain more numbers
            symbol_buffer += symbol
        else:
            if symbol_buffer:
                # Convert number to word and add to list of symbols
                symbols.append(num2words(int(symbol_buffer), lang='pl'))
                symbol_buffer = ''
            symbols.append(symbol)
    if symbol_buffer:
        symbols.append(num2words(int(symbol_buffer), lang='pl'))
    # Join list of symbols back into a string
    return ''.join(symbols)
