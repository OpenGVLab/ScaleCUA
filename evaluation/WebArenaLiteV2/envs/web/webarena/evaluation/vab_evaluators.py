"""base class for evaluation"""

import string
import time
from typing import Any, Optional, Tuple, Union, List, Dict
from urllib.parse import urljoin
import numpy as np
from skimage.metrics import structural_similarity as ssim
import requests
from beartype import beartype
from PIL import Image
from playwright.sync_api import CDPSession, Page

import base64
from io import BytesIO

from envs.web.webarena.evaluation.vab_helper_functions import (
    PseudoPage,
    llm_fuzzy_match,
    llm_ua_match,
    generate_from_openai_chat_completion,
)


class Evaluator(object):
    def __init__(self, eval_tag: str = "") -> None:
        self.eval_tag = eval_tag

    @beartype
    def __call__(
        self, action_list: List, task_config: Dict, page: Page | PseudoPage
    ) -> float:
        raise NotImplementedError

    @staticmethod
    def get_last_response_action(action_list: List) -> str:
        try:
            for action in reversed(action_list):
                if action["name"] == "response":
                    return action["parameters"]["answer"]
            if action_list[-1]["name"] == "terminate":
                return (
                    action_list[-1]["parameters"]["info"]
                    if "info" in action_list[-1]["parameters"]
                    else ""
                )
            else:
                return ""
        except Exception:
            raise ValueError(
                "The last element of action_list should be an action, add a fake stop action if needed"
            )

    @staticmethod
    def get_last_state(action_list: List) -> Any:
        try:
            # is_bearable(action_list[-2], StateInfo)
            last_state = action_list[-2]
        except Exception:
            raise ValueError(
                "The second last element of action_list should be a state, add a fake stop action if needed"
            )

        return last_state  # type: ignore[return-value]


@beartype
class NumericEvaluator(Evaluator):
    """Check if the numerical relationship is correct"""

    @staticmethod
    @beartype
    def str_2_int(s: str) -> Optional[int]:
        try:
            s = s.strip()
            if "," in s:
                s = s.replace(",", "")

            return int(s)
        except ValueError:
            # Return None if the string cannot be converted to int
            print(f"[NumericEvaluator error]: Cannot convert {s} to int")
            return None

    @staticmethod
    @beartype
    def compare_inequality(
        value: Union[int, float], inequality: str, tol: float = 1e-8
    ) -> bool:
        """
        Compare a value (int or float) against an inequality string.

        Args:
        - value (int/float): The value to be compared.
        - inequality (str): Inequality in the form of "< 700", ">= 300", etc.
        - tol (float): Tolerance for floating point comparisons.

        Returns:
        - bool: True if the value satisfies the inequality, False otherwise.
        """
        # Extract the operator and the number from the inequality string
        ops = {
            "<=": lambda x, y: x <= y + tol,
            ">=": lambda x, y: x >= y - tol,
            "==": lambda x, y: abs(x - y) <= tol,
            "<": lambda x, y: x < y + tol,
            ">": lambda x, y: x > y - tol,
        }

        for op, func in ops.items():
            if op in inequality:
                _, num = inequality.split(op)
                return func(value, float(num.strip()))

        raise ValueError(f"Invalid inequality string: {inequality}")


@beartype
class StringEvaluator(Evaluator):
    """Check whether the answer is correct with:
    exact match: the answer is exactly the same as the reference answer
    must include: each phrase in the reference answer must be included in the answer
    fuzzy match: the answer is similar to the reference answer, using LLM judge
    """

    @staticmethod
    @beartype
    def clean_answer(answer: str) -> str:
        if answer.startswith("'") and answer.endswith("'"):
            answer = answer[1:-1]
        elif answer.startswith('"') and answer.endswith('"'):
            answer = answer[1:-1]
        return answer.lower()

    @staticmethod
    @beartype
    def exact_match(ref: str, pred: Union[str, int]) -> float:
        if isinstance(pred, int):
            pred = str(pred)
        return float(
            StringEvaluator.clean_answer(pred) == StringEvaluator.clean_answer(ref)
        )

    @staticmethod
    @beartype
    def must_include(ref: str, pred: str) -> float:
        clean_ref = StringEvaluator.clean_answer(ref)
        clean_pred = StringEvaluator.clean_answer(pred)
        return float(clean_ref in clean_pred)

    @staticmethod
    @beartype
    def must_exclude(ref: str, pred: str) -> float:
        """Returns 1 if pred is not in ref, and 0 otherwise"""
        clean_ref = StringEvaluator.clean_answer(ref)
        clean_pred = StringEvaluator.clean_answer(pred)
        return float(clean_ref in clean_pred)

    @staticmethod
    @beartype
    def fuzzy_match(ref: str, pred: str, intent: str) -> float:
        return llm_fuzzy_match(pred, ref, intent)

    @staticmethod
    @beartype
    def ua_match(ref: str, pred: str, intent: str) -> float:
        return llm_ua_match(pred, ref, intent)

    def __call__(
        self,
        action_list: List,
        task_config: Dict,
        page: Page | PseudoPage | None = None,
    ) -> float:
        pred = self.get_last_response_action(action_list)
        pred = self.clean_answer(pred)

        score = 1.0
        for approach, value in task_config["eval"]["reference_answers"].items():
            match approach:
                case "exact_match":
                    score *= self.exact_match(ref=value, pred=pred)

                case "required_values":
                    required_values = value
                    assert isinstance(required_values, list)
                    pred = NumericEvaluator.str_2_int(pred)
                    if pred is None:
                        score = 0.0
                    else:
                        for v in required_values:
                            value_or = v.split(" |OR| ")
                            score *= any(
                                [
                                    NumericEvaluator.compare_inequality(pred, value)
                                    for value in value_or
                                ]
                            )

                case "must_include":
                    assert isinstance(value, list)
                    for must_value in value:
                        value_or = must_value.split(" |OR| ")
                        score *= any(
                            [self.must_include(ref=v, pred=pred) for v in value_or]
                        )

                case "must_exclude":
                    assert isinstance(value, list)
                    for must_excl_value in value:
                        score *= self.must_exclude(ref=must_excl_value, pred=pred)

                case "one_of":
                    assert isinstance(value, list)
                    found = False
                    for one_of_value in value:
                        one_of_value = self.clean_answer(one_of_value)
                        if one_of_value in pred:
                            found = True
                            break
                    score = score * found

                case "fuzzy_match":
                    intent = task_config["intent"]
                    if value == "N/A":
                        # if the instruction only asks the model to generate N/A when encountering an unachievable task
                        # without more concrete reasons
                        score *= self.exact_match(ref=value, pred=pred)
                        # if the instruction also asks the model to generate the reason why the task is unachievable
                        # this should be the default as it will prevent false positive N/A`
                        if score != 1:
                            score = 1.0 * self.ua_match(
                                intent=task_config["intent"],
                                ref=task_config["eval"]["string_note"],
                                pred=pred,
                            )
                    else:
                        assert isinstance(value, list)
                        reference = ", ".join(value)
                        if pred != "":
                            score *= self.fuzzy_match(
                                ref=reference, pred=pred, intent=intent
                            )
                        else:
                            score *= 0
        return score


# @beartype
# class StringSoftEvaluator(Evaluator):
#     """Use text generation metrics such as BLEU, ROUGE, etc. to evaluate the answer"""

#     def __call__(
#         self,
#         action_list: List,
#         task_config: Dict,
#         page: Page | PseudoPage | None = None
#     ) -> float:

#         last_action = self.get_last_response_action(action_list)
#         # 获取最后一个动作，但其实应该是倒数第二个动作
#         pred = last_action["parameters"]["answer"]
#         ref = task_config["eval"]["reference_answers"]
#         # rouge
#         m = evaluate.load("rouge")
#         rouge = m.compute(predictions=[pred], references=[ref])
#         return float(rouge["rouge1"])


@beartype
class URLExactEvaluator(Evaluator):
    """Check whether the URL is exactly the same as of the reference URLs"""

    def __call__(
        self, action_list: List, task_config: Dict, page: Page | PseudoPage
    ) -> float:

        def clean_url(url: str) -> str:
            url = str(url)
            # Replace http://localhost with http://127.0.0.1 to keep things consistent across evals.
            url = url.replace("localhost", "127.0.0.1")
            if url.endswith("/"):
                url = url[:-1]
            return url

        pred = clean_url(page.url)
        print(f"Pred Url: {pred}")
        ref_urls = task_config["eval"]["reference_url"].split(" |OR| ")
        ref_urls = [clean_url(url) for url in ref_urls]
        print(f"Ref Url: {ref_urls}")
        matching_rule = task_config["eval"].get("url_note", "EXACT")
        if matching_rule == "EXACT":
            if pred in ref_urls:
                return 1.0
            else:
                return 0.0
        elif matching_rule == "GOLD in PRED":
            if any([ref in pred for ref in ref_urls]):
                return 1.0
            else:
                return 0.0
        else:
            raise ValueError(f"Unknown matching rule: {matching_rule}")


@beartype
class HTMLContentExactEvaluator(Evaluator):
    """Check whether the contents appear in the page"""

    @staticmethod
    @beartype
    def fuzzy_match(ref: str, pred: str, intent: str) -> float:
        return llm_fuzzy_match(pred, ref, intent)

    def __call__(
        self, action_list: List, task_config: Dict, page: Page | PseudoPage
    ) -> float:

        targets = task_config["eval"]["program_html"]

        score = 1.0
        for target in targets:
            target_url: str = target["url"]  # which url to check
            if target_url.startswith("func"):
                func = target_url.split("func:")[1]
                func = func.replace("__last_url__", page.url)
                target_url = eval(func)

            locator: str = target["locator"]  # js element locator

            # navigate to that url
            if target_url != "last":
                page.goto(target_url)
                time.sleep(3)

            # empty, use the full page
            if not locator.strip():
                selected_element = page.content()
            # use JS to select the element
            elif locator.startswith("document.") or locator.startswith("[...document."):
                if "prep_actions" in target:
                    try:
                        for prep_action in target["prep_actions"]:
                            page.evaluate(f"() => {prep_action}")
                    except Exception:
                        pass
                try:
                    selected_element = str(page.evaluate(f"() => {locator}"))
                    if not selected_element:
                        selected_element = ""
                except Exception:
                    # the page is wrong, return empty
                    selected_element = ""
            elif locator.startswith("lambda:"):
                try:
                    locator = locator.lstrip("lambda:")
                    selected_element = page.evaluate(locator)
                    if not selected_element:
                        selected_element = None
                except Exception:
                    # the page is wrong, return empty
                    selected_element = None
            # run program to call API
            elif locator.startswith("func:"):  # a helper function
                func = locator.split("func:")[1]
                func = func.replace("__page__", "page")
                selected_element = eval(func)
            else:
                raise ValueError(f"Unknown locator: {locator}")

            # If the selected element is None, then the page is wrong
            if selected_element is None:
                score = 0.0
                break

            if "exact_match" in target["required_contents"]:
                required_contents = target["required_contents"]["exact_match"]
                score *= StringEvaluator.exact_match(
                    ref=required_contents, pred=selected_element
                )
            elif "must_include" in target["required_contents"]:
                required_contents = target["required_contents"]["must_include"]
                assert isinstance(required_contents, list)
                for content in required_contents:
                    content_or = content.split(" |OR| ")
                    score *= any(
                        [
                            StringEvaluator.must_include(
                                ref=content, pred=selected_element
                            )
                            for content in content_or
                        ]
                    )
            elif "must_exclude" in target["required_contents"]:
                required_contents = target["required_contents"]["must_exclude"]
                assert isinstance(required_contents, list)
                for content in required_contents:
                    assert " |OR| " not in content
                    score *= StringEvaluator.must_exclude(
                        content, pred=selected_element
                    )
            elif "required_values" in target["required_contents"]:
                required_values = target["required_contents"]["required_values"]
                assert isinstance(required_values, list)
                if isinstance(selected_element, str):
                    selected_element = NumericEvaluator.str_2_int(selected_element)
                if selected_element is None:
                    score = 0.0
                else:
                    for value in required_values:
                        value_or = value.split(" |OR| ")
                        score *= any(
                            [
                                NumericEvaluator.compare_inequality(
                                    selected_element, value
                                )
                                for value in value_or
                            ]
                        )
            elif "fuzzy_match" in target["required_contents"]:
                required_contents = target["required_contents"]["fuzzy_match"]
                intent = task_config["intent"]

                assert isinstance(required_contents, list)
                reference = ", ".join(required_contents)
                score *= self.fuzzy_match(
                    ref=reference, pred=selected_element, intent=intent
                )
            else:
                raise ValueError(
                    f"Unknown required_contents: {target['required_contents'].keys()}"
                )

        return score


def get_image_ssim(image_pixels, exact_match_pixels):
    """
    Calculate the Structural Similarity Index (SSIM) between two images.

    Args:
        image_pixels (PIL.Image.Image): The first image to compare.
        exact_match_pixels (PIL.Image.Image): The second image to compare.

    Returns:
        float: SSIM value between the two images, in the range [0, 1].
    """
    # Convert both images to grayscale for SSIM comparison
    image1 = image_pixels.convert("L")
    image2 = exact_match_pixels.convert("L")

    # Resize the images to the same size if they differ
    if image1.size != image2.size:
        image2 = image2.resize(image1.size)

    # Convert images to numpy arrays
    image1_np = np.array(image1)
    image2_np = np.array(image2)

    # Compute SSIM
    ssim_value = ssim(image1_np, image2_np)

    return ssim_value


@beartype
class PageImageEvaluator(Evaluator):
    """Check whether the answer is correct by querying a vision model."""

    def __init__(self):
        # Default to 0.8 as the threshold for similarity to account for compression, resizing, etc
        # This might be too generous but we bias towards minimizing false negatives.
        self.ssim_threshold = 0.8

    @staticmethod
    def captioning_fn(
        all_image_pixels: List[Image.Image],
        prompts: List[str],
        model: str = "gpt-4o-2024-11-20",
        temperature: float = 0.7,
        max_tokens: int = 2048,
        top_p: float = 1.0,
        context_length: int = 4096,
        stop_token: str | None = None,
    ) -> List[str]:
        """
        Generate captions or answers for a list of images using an LLM.

        Args:
            all_image_pixels (List[Image.Image]): A list of image objects.
            prompts (List[str]): Prompts/questions for each image.
            model (str): The model version to use (default: gpt-4o-2024-11-20).
            temperature (float): Sampling temperature for the LLM.
            max_tokens (int): Maximum tokens to generate in the response.
            top_p (float): Top-p sampling for the LLM.
            context_length (int): Maximum context size for the LLM.
            stop_token (str | None): Optional stop token for truncating responses.

        Returns:
            List[str]: Responses from the LLM for each prompt.
        """
        responses = []

        # Process each image and prompt
        for image, prompt in zip(all_image_pixels, prompts):
            try:
                # Convert the image to Base64-encoded string
                buffered = BytesIO()
                image.save(buffered, format="PNG")
                encoded_string = base64.b64encode(buffered.getvalue()).decode("utf-8")

                # Prepare the messages in the required format
                messages = [
                    {
                        "role": "system",
                        "content": "You are a GUI helpful assistant, please answer my question.",
                    },
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{encoded_string}"
                                },
                            },
                            {
                                "type": "text",
                                "text": prompt,
                            },
                        ],
                    },
                ]

                # Call the OpenAI API using the provided function
                response = generate_from_openai_chat_completion(
                    messages=messages,
                    model=model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    top_p=top_p,
                    context_length=context_length,
                    stop_token=stop_token,
                )

                responses.append(response)
            except Exception as e:
                # Append an error response if something goes wrong
                responses.append(f"[ERROR]: {str(e)}")

        return responses

    def __call__(
        self,
        action_list: List,
        task_config: Dict,
        page: Page | PseudoPage | None = None,
    ) -> float:
        score = 1.0

        for query in task_config["eval"]["page_image_query"]:
            locator: str = query["eval_image_class"]
            target_url: str = query["eval_image_url"]
            if target_url.startswith("func"):
                func = target_url.split("func:")[1]
                func = func.replace("__last_url__", page.url)
                target_url = eval(func)

            # navigate to that url
            if target_url != "last":
                page.goto(target_url)
                time.sleep(3)

            # empty, use the full page
            if not locator.strip():
                images = page.get_by_role("img").all()
            # use JS to select the element
            elif locator.startswith("."):
                # Get all img children under the locator
                elements = page.query_selector_all(locator)
                images = []
                for element in elements:
                    is_img = element.evaluate('element => element.tagName === "IMG"')
                    if is_img:
                        images.append(element)
                    else:
                        images.extend(element.query_selector_all("img"))
            else:
                raise ValueError(f"Unknown locator: {locator}")

            if images == []:
                return 0.0

            all_image_pixels = []
            for image in images:
                try:
                    # Get image from URL.
                    image_url = image.get_attribute("src")
                    if not image_url.startswith(("http://", "https://", "www.")):
                        image_url = urljoin(page.url, image_url)
                    image = Image.open(requests.get(image_url, stream=True).raw)
                    all_image_pixels.append(image)
                except Exception as e:
                    print("[WARNING]: ", e)

            if all_image_pixels == []:
                return 0.0
            else:
                # Run the VQA eval on the image elements.
                eval_vqas = query.get("eval_vqa", [])
                assert (
                    len(eval_vqas) > 0 or "eval_fuzzy_image_match" in query
                ), "eval_vqa must have at least 2 questions or eval_fuzzy_image_match must be True"
                for qa in eval_vqas:
                    question, answer = qa["question"], qa["answer"]
                    prompt = f"Q: {question} A:"
                    pred_ans = PageImageEvaluator.captioning_fn(
                        all_image_pixels, [prompt] * len(all_image_pixels)
                    )
                    score *= float(
                        any([answer.lower() in ans.lower() for ans in pred_ans])
                    )

                if "eval_fuzzy_image_match" in query:
                    ssim_threshold = query.get("ssim_threshold", self.ssim_threshold)
                    exact_match_imgs = query["eval_fuzzy_image_match"].split(" |OR| ")
                    all_exact_match_pixels = []

                    for exact_match_img in exact_match_imgs:
                        if exact_match_img.startswith("http"):
                            exact_match_pixels = Image.open(
                                requests.get(exact_match_img, stream=True).raw
                            )
                        else:
                            exact_match_pixels = Image.open(exact_match_img)
                        all_exact_match_pixels.append(exact_match_pixels)

                    # Check if any of the images on the page match
                    found_exact_match = False
                    for exact_match_pixels in all_exact_match_pixels:
                        for image_pixels in all_image_pixels:
                            ssim = get_image_ssim(image_pixels, exact_match_pixels)
                            if ssim > ssim_threshold:
                                found_exact_match = True
                                break
                    score *= float(found_exact_match)

        return score


class EvaluatorComb:
    def __init__(self, evaluators: list[Evaluator]) -> None:
        self.evaluators = evaluators

    def __call__(
        self, action_list: List, task_config: Dict, page: Page | PseudoPage
    ) -> float:

        score = 1.0
        for evaluator in self.evaluators:
            cur_score = evaluator(action_list, task_config, page)
            score *= cur_score

        return score


@beartype
def webarena_evaluator_router(task_config: dict, captioning_fn=None) -> EvaluatorComb:
    """Router to get the evaluator class"""
    eval_types = task_config["eval"]["eval_types"]
    evaluators: list[Evaluator] = []
    for eval_type in eval_types:
        match eval_type:
            case "string_match":
                evaluators.append(StringEvaluator())
            case "url_match":
                evaluators.append(URLExactEvaluator())
            case "program_html":
                evaluators.append(HTMLContentExactEvaluator())
            case "page_image_query":
                evaluators.append(PageImageEvaluator())
            case _:
                raise ValueError(f"eval_type {eval_type} is not supported")

    return EvaluatorComb(evaluators)
