from num2words import num2words
from logger import logger


async def fix_numbers(text):
    """
    Convert numeric digits in text to their word representation.

    Args:
        text (str): Text containing numeric digits to convert

    Returns:
        str: Text with numeric digits converted to words
    """
    try:
        symbols = []
        symbol_buffer = ''

        for symbol in text:
            if symbol.isnumeric():
                # Add numeric symbol to buffer because it might contain more numbers
                symbol_buffer += symbol
            else:
                if symbol_buffer:
                    # Convert number to word and add to list of symbols
                    try:
                        symbols.append(num2words(int(symbol_buffer), lang='pl'))
                    except ValueError as e:
                        logger.warning(f"Could not convert number '{symbol_buffer}': {e}")
                        symbols.append(symbol_buffer)
                    symbol_buffer = ''
                symbols.append(symbol)

        # Don't forget to process any remaining numbers in the buffer
        if symbol_buffer:
            try:
                symbols.append(num2words(int(symbol_buffer), lang='pl'))
            except ValueError as e:
                logger.warning(f"Could not convert number '{symbol_buffer}': {e}")
                symbols.append(symbol_buffer)

        # Join list of symbols back into a string
        return ''.join(symbols)

    except Exception as e:
        logger.error(f"Error in fix_numbers: {e}")
        # Return original text if there's an error
        return text
