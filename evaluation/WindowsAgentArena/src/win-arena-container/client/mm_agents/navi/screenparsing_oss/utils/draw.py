from PIL import ImageDraw
import copy

def draw_ents(image, ents, labelKey='text'):
    image = copy.copy(image)
    draw = ImageDraw.Draw(image)
    for ent in ents:
        color = 'red'
        shape = ent['shape']
        x, y, width, height = shape['x'], shape['y'], shape['width'], shape['height']
        draw.rectangle([x, y, x + width, y + height], outline=color, width=2)
        if ent.get(labelKey):
            draw.text((x, y - 10), ent.get(labelKey), fill=color)
    return image