import re
from logger import logger


async def split_message(text):
    """
    Split a message into tokens for processing.
    
    This function splits the input text into individual tokens, handling special formatting:
    - Square brackets [] for sound effects
    - Curly brackets {} for voice effects
    - Regular text is kept together
    
    Args:
        text (str): The input text to split
        
    Returns:
        list: A list of tokens extracted from the text
    """
    try:
        if not text or not isinstance(text, str):
            logger.warning(f"Invalid input to split_message: {text}")
            return []
            
        # Split the string into individual tokens (words, square brackets, curly brackets)
        pattern = r'\[[^\]]*\]|\{[^\}]*\}|[^\[\]\{\} ]+'
        tokens = re.findall(pattern, text)
        
        if not tokens:
            return []
            
        # Merge non-bracketed and non-curly-bracketed words that appear next to each other
        merged_tokens = []
        for token in tokens:
            # If the current token is not bracketed and the last token is also not bracketed,
            # merge them with a space
            if (merged_tokens and 
                not re.match(r'(\[.*\]|\{.*\})', token) and 
                not re.match(r'(\[.*\]|\{.*\})', merged_tokens[-1])):
                merged_tokens[-1] += ' ' + token
            else:
                merged_tokens.append(token)
                
        logger.debug(f"Split message into {len(merged_tokens)} tokens")
        return merged_tokens
        
    except Exception as e:
        logger.error(f"Error in split_message: {e}")
        # Return the original text as a single token if there's an error
        return [text] if text else []
