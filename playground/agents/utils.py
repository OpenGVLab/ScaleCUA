import re
import ast
import math
from PIL import Image
import io

IMAGE_FACTOR = 28
MIN_PIXELS = 3136
MAX_PIXELS = 2109744
MAX_RATIO = 200
def encoded_img_to_pil_img(data_str):
    image = Image.open(io.BytesIO(data_str))
    return image
    
def escape_single_quotes(text):

    pattern = r"(?<!\\)'"
    return re.sub(pattern, r"\\'", text)

def round_by_factor(number: int, factor: int) -> int:
    """Returns the closest integer to 'number' that is divisible by 'factor'."""
    return round(number / factor) * factor


def ceil_by_factor(number: int, factor: int) -> int:
    """Returns the smallest integer greater than or equal to 'number' that is divisible by 'factor'."""
    return math.ceil(number / factor) * factor


def floor_by_factor(number: int, factor: int) -> int:
    """Returns the largest integer less than or equal to 'number' that is divisible by 'factor'."""
    return math.floor(number / factor) * factor




def smart_resize(
    height: int, width: int, factor: int = IMAGE_FACTOR, min_pixels: int = MIN_PIXELS, max_pixels: int = MAX_PIXELS
) -> tuple[int, int]:
    """
    Rescales the image so that the following conditions are met:

    1. Both dimensions (height and width) are divisible by 'factor'.

    2. The total number of pixels is within the range ['min_pixels', 'max_pixels'].

    3. The aspect ratio of the image is maintained as closely as possible.
    """
    if max(height, width) / min(height, width) > MAX_RATIO:
        raise ValueError(
            f"absolute aspect ratio must be smaller than {MAX_RATIO}, got {max(height, width) / min(height, width)}"
        )
    h_bar = max(factor, round_by_factor(height, factor))
    w_bar = max(factor, round_by_factor(width, factor))
    if h_bar * w_bar > max_pixels:
        beta = math.sqrt((height * width) / max_pixels)
        h_bar = floor_by_factor(height / beta, factor)
        w_bar = floor_by_factor(width / beta, factor)
    elif h_bar * w_bar < min_pixels:
        beta = math.sqrt(min_pixels / (height * width))
        h_bar = ceil_by_factor(height * beta, factor)
        w_bar = ceil_by_factor(width * beta, factor)
    return h_bar, w_bar

def parse_point_from_string(s):
    # Define patterns for different coordinate formats
    patterns = [
        # Match <box>[[x1,y1,x2,y2]]</box> pattern
        r'<box>\[\[([^]]+)\]\]</box>',
        # Match 'x=x1,y=y1' pattern (with possible quotes and whitespace)
        r'x\s*=\s*([\d\.\-]+)\s*,\s*y\s*=\s*([\d\.\-]+)',
        # Match (x1,y1) pattern (with possible quotes)
        r'\(([\d\.\-]+)\s*,\s*([\d\.\-]+)\)'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, s)
        if match:
            if pattern == patterns[0]:  # box pattern
                try:
                    coords = [float(x.strip()) for x in match.group(1).split(',')]
                    if len(coords) == 4:
                        # Calculate bbox center
                        x_center = (coords[0] + coords[2]) / 2
                        y_center = (coords[1] + coords[3]) / 2
                        return (x_center, y_center)
                except (ValueError, SyntaxError):
                    continue
            else:  # other patterns
                try:
                    x = float(match.group(1).strip())
                    y = float(match.group(2).strip())
                    return (x, y)
                except (ValueError, SyntaxError):
                    continue
    
    return None  # No matching pattern found

if __name__ == "__main__":
    test_strings = [
        "Some text <box>[[10,20,30,40]]</box> more text",
        "Coordinates are '(x=5.5,y=7.2)' in the image",
        "The point is (3, 4) in the diagram",
        "Another example <box>[[1.2,3.4,5.6,7.8]]</box>",
        "Position: x=100, y=200",
        "Location (3.1415, 2.7182)",
    ]
    for test in test_strings:
        result = parse_point_from_string(test)
        print(f"Input: {test}\nOutput: {result}\n")


