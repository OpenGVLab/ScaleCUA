import math
import re
from collections import deque


def bounds_to_coords(bounds_string):
    pattern = r"\[(-?\d+),(-?\d+)\]\[(-?\d+),(-?\d+)\]"
    matches = re.findall(pattern, bounds_string)
    return list(map(int, matches[0]))


def coords_to_bounds(bounds):
    return f"[{bounds[0]},{bounds[1]}][{bounds[2]},{bounds[3]}]"


def check_valid_bounds(bounds):
    bounds = bounds_to_coords(bounds)

    return bounds[0] >= 0 and bounds[1] >= 0 and \
        bounds[0] < bounds[2] and bounds[1] < bounds[3]


def check_point_containing(bounds, x, y, window, threshold=0):
    bounds = bounds_to_coords(bounds)

    screen_threshold_x = threshold * window[0]
    screen_threshold_y = threshold * window[1]

    return bounds[0] - screen_threshold_x <= x <= bounds[2] + screen_threshold_x and \
        bounds[1] - screen_threshold_y <= y <= bounds[3] + screen_threshold_y


def check_bounds_containing(bounds_contained, bounds_containing):
    bounds_contained = bounds_to_coords(bounds_contained)
    bounds_containing = bounds_to_coords(bounds_containing)

    return bounds_contained[0] >= bounds_containing[0] and \
        bounds_contained[1] >= bounds_containing[1] and \
        bounds_contained[2] <= bounds_containing[2] and \
        bounds_contained[3] <= bounds_containing[3]


def check_bounds_intersection(bounds1, bounds2):
    bounds1 = bounds_to_coords(bounds1)
    bounds2 = bounds_to_coords(bounds2)

    return bounds1[0] < bounds2[2] and bounds1[2] > bounds2[0] and \
        bounds1[1] < bounds2[3] and bounds1[3] > bounds2[1]


def get_bounds_area(bounds):
    bounds = bounds_to_coords(bounds)
    return (bounds[2] - bounds[0]) * (bounds[3] - bounds[1])


def get_bounds_center(bounds):
    bounds = bounds_to_coords(bounds)
    return (bounds[0] + bounds[2]) // 2, (bounds[1] + bounds[3]) // 2


def calculate_point_distance(x1, y1, x2, y2):
    distance = math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)
    return distance


def compare_bounds_area(bounds1, bounds2):
    """
    :return:
        if bounds1 is smaller than bounds2, return true
        else return false
    """
    return get_bounds_area(bounds1) < get_bounds_area(bounds2)


def compare_y_in_bounds(bounds1, bounds2):
    """
    :return:
        if y in bounds1 is smaller than that in bounds2, return true
        else return false
    """
    bounds1 = bounds_to_coords(bounds1)
    bounds2 = bounds_to_coords(bounds2)

    return bounds1[1] < bounds2[1] and bounds1[3] < bounds2[3]
