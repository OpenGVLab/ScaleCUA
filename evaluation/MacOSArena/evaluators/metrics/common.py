from typing import List, Union

def find_str(value: str, keyword: str) -> bool:
    """
    Checks if the keyword is a substring of the given value.

    :param value: The full string to search within.
    :param keyword: The substring to look for.
    :return: True if keyword exists in value, else False.
    """
    return keyword in value

def find_str_in_list(value: Union[str, List[str]], keyword: Union[str, List[str]]) -> bool:
    """
    Checks if any item in `value` contains the keyword(s).

    - If `value` is a str, treat it as a single-item list.
    - If `keyword` is str: return True if any item in `value` contains it.
    - If `keyword` is list[str]: return True if any item in `value` contains ALL strings in `keyword`.

    :param value: A string or list of strings to search within.
    :param keyword: A string or list of strings to search for.
    :return: True if matching condition is met, False otherwise.
    """
    if isinstance(value, str):
        value = [value]

    if isinstance(keyword, str):
        return any(keyword in v for v in value)
    elif isinstance(keyword, list):
        return any(all(k in v for k in keyword) for v in value)
    else:
        raise TypeError("Keyword must be a string or a list of strings")
    
def find_str_in_list_ci(value: List[str], keyword: Union[str, List[str]]) -> bool:
    """
    Case-insensitive version of find_str_in_list:
    Checks if any item in `value` contains the keyword(s), ignoring case.

    - If keyword is str: return True if any item in value contains it (case-insensitive).
    - If keyword is list[str]: return True if any item in value contains ALL strings in keyword (case-insensitive).

    :param value: List of strings to search within.
    :param keyword: A string or list of strings to search for.
    :return: True if matching condition is met, False otherwise.
    """
    lowered_value = [v.lower() for v in value]

    if isinstance(keyword, str):
        keyword_lower = keyword.lower()
        return any(keyword_lower in v for v in lowered_value)
    elif isinstance(keyword, list):
        keyword_lower_list = [k.lower() for k in keyword]
        return any(all(k in v for k in keyword_lower_list) for v in lowered_value)
    else:
        raise TypeError("Keyword must be a string or a list of strings")


def find_dict(dict_list: list[dict], target: dict) -> bool:
    """
    Checks if the target dictionary is a subset of any dictionary in the list.

    :param target: The key-value pairs to match.
    :param dict_list: The list of dictionaries to search within.
    :return: True if any dictionary in the list contains all items in target, else False.
    """
    for d in dict_list:
        if all(item in d.items() for item in target.items()):
            return True
    return False


def exact_match(value: str, expected: str) -> bool:
    """
    Checks if the value exactly matches the expected string.

    :param value: Actual value.
    :param expected: Expected value to match against.
    :return: True if exactly equal, else False.
    """
    return value == expected


def dict_equal(value: dict, expected: dict) -> bool:
    """
    Check if two dictionaries are exactly equal.

    :param value: The actual dictionary.
    :param expected: The expected dictionary.
    :return: True if both dictionaries are equal, False otherwise.
    """
    if not isinstance(value, dict) or not isinstance(expected, dict):
        return False
    return value == expected

def is_true(value) -> bool:
    """
    Checks if the value is explicitly True (boolean type).

    :param value: Value to evaluate.
    :return: True if value is True, else False.
    """
    return value is True

def is_false(value) -> bool:
    """
    Checks if the value is explicitly False (boolean type).

    :param value: Value to evaluate.
    :return: True if value is False, else False.
    """
    return value is False

def check_list_length(lst: list, op: str, number: int) -> bool:
    """
    Compares the length of a list against a given number using an operator.

    :param lst: The list to evaluate.
    :param op: A comparison operator string: ">", "<", "==", ">=", "<=", "!=".
    :param number: The number to compare against.
    :return: True if the comparison holds, False otherwise.
    """
    length = len(lst)
    if op == ">":
        return length > number
    elif op == "<":
        return length < number
    elif op == "==":
        return length == number
    elif op == ">=":
        return length >= number
    elif op == "<=":
        return length <= number
    elif op == "!=":
        return length != number
    else:
        raise ValueError(f"Unsupported operator: {op}")
    
def compare_numbers(a: float, op: str, b: float) -> bool:
    """
    Compares two numbers using a specified operator.

    :param a: The first number.
    :param op: A comparison operator string: ">", "<", "==", ">=", "<=", "!=".
    :param b: The second number.
    :return: True if the comparison is valid, False otherwise.
    """
    if op == ">":
        return a > b
    elif op == "<":
        return a < b
    elif op == "==":
        return a == b
    elif op == ">=":
        return a >= b
    elif op == "<=":
        return a <= b
    elif op == "!=":
        return a != b
    else:
        raise ValueError(f"Unsupported operator: {op}")

def contains_element(lst: list, element: str) -> bool:
    """
    Checks if a specific element exists in the list.

    :param lst: The list to search in.
    :param element: The element to look for.
    :return: True if element exists in the list, False otherwise.
    """
    return element in lst

def check_list_length_and_contains_element(lst: list, op: str, number: int, element: str):
    return check_list_length(lst, op, number) and contains_element(lst, element)
