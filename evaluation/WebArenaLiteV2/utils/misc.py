import io
import math
import re
import time

from PIL import Image, ImageDraw


def draw_xy(image_path, x, y, save_path):
    """
    Draw a red X marker at the specified relative coordinates (0-1) on an image and save the result.

    Args:
        image_path (str): Path to the original image.
        x (float): Relative x-coordinate in range [0, 1].
        y (float): Relative y-coordinate in range [0, 1].
        save_path (str): Path where the modified image will be saved.

    Returns:
        None
    """
    # Skip if coordinates are not provided
    if x is None or y is None:
        return

    # Open the image
    img = Image.open(image_path)
    width, height = img.size  # Get image dimensions

    # Convert relative coordinates to absolute if they are in range [0, 1]
    if 0 <= x < 1 and 0 <= y < 1:
        x = int(x * width)
        y = int(y * height)

    # Draw a red X marker on the image
    draw = ImageDraw.Draw(img)
    line_length = min(width, height) // 20  # X marker size, adjusted to image dimensions
    line_thickness = max(1, min(width, height) // 200)  # Line thickness

    # Draw two crossing lines: top-left to bottom-right & bottom-left to top-right
    draw.line(
        [(x - line_length, y - line_length), (x + line_length, y + line_length)],
        fill="red",
        width=line_thickness
    )
    draw.line(
        [(x - line_length, y + line_length), (x + line_length, y - line_length)],
        fill="red",
        width=line_thickness
    )

    # Save the modified image
    img.save(save_path)
    img.close()

def call_llm_safe(agent):
    # Retry if fails
    max_retries = 10  # Set the maximum number of retries
    attempt = 0
    response = ""
    while attempt < max_retries:
        try:
            response = agent.get_response()
            break  # If successful, break out of the loop
        except Exception as e:
            attempt += 1
            print(f"Attempt {attempt} failed: {e}")
            if attempt == max_retries:
                print("Max retries reached. Handling failure.")
        time.sleep(2.0)
    return response

IMAGE_FACTOR = 28
MIN_PIXELS = 100 * 28 * 28
MAX_PIXELS = 16384 * 28 * 28
MAX_RATIO = 200

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

def encoded_img_to_pil_img(data_str):
    image = Image.open(io.BytesIO(data_str))
    return image

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

# Template for storing task results
RESULT_TEMPLATE = {
    "task_id": None,  # Unique identifier for the task
    "task": None,  # Description of the task
    "final_result_response": "",  # Final response or result of the task execution
    "steps": None  # Number of steps taken to complete the task
}