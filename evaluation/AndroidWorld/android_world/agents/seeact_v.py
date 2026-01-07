# Copyright 2024 The android_world Authors.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""A Multimodal Autonomous Agent for Android (M3A)."""
import re
import io
import time

import ast
import json
import numpy as np
from PIL import Image
from openai import OpenAI
from android_world.agents.PROMPT import *
import re

from openai import OpenAI
import time
import numpy as np
from android_world.env import interface
from android_world.env import json_action
from android_world.agents import base_agent
import base64
import cv2
from android_world.agents import agent_utils
from android_world.agents import base_agent
from android_world.agents import infer
from android_world.agents import m3a_utils
from android_world.agents.utils import *
from android_world.env import interface
from android_world.env import json_action
from android_world.env import representation_utils

try:
    from transformers.models.qwen2_vl.image_processing_qwen2_vl_fast import (  # type: ignore
        smart_resize,
    )
except Exception:  # pragma: no cover
    smart_resize = None  # type: ignore[assignment]

# Utils for Visual Grounding


def _action_selection_prompt_locate(
    goal: str,
    history: list[str],
    ui_elements: str,
    additional_guidelines: list[str] | None = None,
) -> str:
    """Generate the prompt for the action selection.

    Args:
      goal: The current goal.
      history: Summaries for previous steps.
      ui_elements: A list of descriptions for the UI elements.
      additional_guidelines: Task specific guidelines.

    Returns:
      The text prompt for action selection that will be sent to gpt4v.
    """
    if history:
        history = "\n".join(history)
    else:
        history = "You just started, no action has been performed yet."

    extra_guidelines = ""
    if additional_guidelines:
        extra_guidelines = "For The Current Task:\n"
        for guideline in additional_guidelines:
            extra_guidelines += f"- {guideline}\n"

    return ACTION_SELECTION_PROMPT_TEMPLATE_LOCATE.format(
        goal=goal,
        history=history,
        additional_guidelines=extra_guidelines,
    )


def _generate_ui_element_description(
    ui_element: representation_utils.UIElement, index: int
) -> str:
    """Generate a description for a given UI element with important information.

    Args:
      ui_element: UI elements for the current screen.
      index: The numeric index for the UI element.

    Returns:
      The description for the UI element.
    """
    element_description = f'UI element {index}: {{"index": {index}, }}'
    if ui_element.text:
        element_description += f'"text": "{ui_element.text}", '
    if ui_element.content_description:
        element_description += (
            f'"content_description": "{ui_element.content_description}", '
        )
    if ui_element.hint_text:
        element_description += f'"hint_text": "{ui_element.hint_text}", '
    if ui_element.tooltip:
        element_description += f'"tooltip": "{ui_element.tooltip}", '
    element_description += (
        f'"is_clickable": {"True" if ui_element.is_clickable else "False"}, '
    )
    element_description += (
        '"is_long_clickable":'
        f' {"True" if ui_element.is_long_clickable else "False"}, '
    )
    element_description += (
        f'"is_editable": {"True" if ui_element.is_editable else "False"}, '
    )
    if ui_element.is_scrollable:
        element_description += '"is_scrollable": True, '
    if ui_element.is_focusable:
        element_description += '"is_focusable": True, '
    element_description += (
        f'"is_selected": {"True" if ui_element.is_selected else "False"}, '
    )
    element_description += (
        f'"is_checked": {"True" if ui_element.is_checked else "False"}, '
    )
    return element_description[:-2] + "}"


def _generate_ui_elements_description_list(
    ui_elements: list[representation_utils.UIElement],
    screen_width_height_px: tuple[int, int],
) -> str:
    """Generate concise information for a list of UIElement.

    Args:
      ui_elements: UI elements for the current screen.
      screen_width_height_px: The height and width of the screen in pixels.

    Returns:
      Concise information for each UIElement.
    """
    tree_info = ""
    for index, ui_element in enumerate(ui_elements):
        if m3a_utils.validate_ui_element(ui_element, screen_width_height_px):
            tree_info += _generate_ui_element_description(ui_element, index) + "\n"
    return tree_info


def _summarize_prompt(
    action: str,
    reason: str,
    goal: str,
    before_elements: str,
    after_elements: str,
) -> str:
    """Generate the prompt for the summarization step.

    Args:
      action: Action picked.
      reason: The reason to pick the action.
      goal: The overall goal.
      before_elements: Information for UI elements on the before screenshot.
      after_elements: Information for UI elements on the after screenshot.

    Returns:
      The text prompt for summarization that will be sent to gpt4v.
    """
    return SUMMARY_PROMPT_TEMPLATE.format(
        goal=goal,
        before_elements=before_elements,
        after_elements=after_elements,
        action=action,
        reason=reason,
    )


class InternVL(base_agent.EnvironmentInteractingAgent):
    def __init__(
        self,
        env: interface.AsyncEnv,
        llm: infer.MultimodalLlmWrapper,
        name: str = "M3A",
        wait_after_action_seconds: float = 2.0,
        model_address="http://10.140.60.2:10020/",
        model_api_key="gui_v89",
        model_name="",
    ):
        super().__init__(env, name)
        self.llm = llm
        self.history = []
        self.additional_guidelines = None
        self.wait_after_action_seconds = wait_after_action_seconds
        print(f"{model_address}v1")
        self.model_client = OpenAI(base_url=f"{model_address}v1", api_key=model_api_key)
        self.step_his: str = ""
        self.turn_number: int = 0
        self.model_name = model_name
        self.last_action = None
        self.repeat_time = 0

    def step(self, instruction: str) -> base_agent.AgentInteractionResult:
        self.turn_number += 1
        state = self.get_post_transition_state()
        screenshot = state.pixels.copy()
        height, width = screenshot.shape[:2]

        system_prompt = internvl2_5_mobile_planning_cot_v1
        user_prompt = android_user_prompt.format(
            instruction=instruction, actions=self.step_his
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": self._to_base64_png(screenshot)},
                    },
                    {"type": "text", "text": user_prompt},
                ],
            },
        ]
        completion = self.model_client.chat.completions.create(
            model=self.model_name, messages=messages, temperature=0
        )
        response = completion.choices[0].message.content
        print(response)
        print("=" * 50)
        # Extract operation and actions
        op_m = re.search(r"<operation>([\s\S]*?)</operation>", response)
        act_m = re.search(r"<action>([\s\S]*?)</action>", response)
        op_text = op_m.group(1).strip() if op_m else ""
        self.step_his += f"Step {self.turn_number}: {op_text}\n"

        if not act_m:
            return base_agent.AgentInteractionResult(
                True, {"summary": "No valid action returned."}
            )
        if self.last_action == act_m.group(1):
            # return base_agent.AgentInteractionResult(True, {'operation': op_text, 'response': response})
            self.repeat_time += 1
        else:
            self.repeat_time = 0
        self.last_action = act_m.group(1)
        # Execute each parsed action
        cmds = [l for l in act_m.group(1).splitlines() if l.strip()]
        print(cmds)
        for cmd in cmds:
            parsed = action_transform(cmd, width, height)
            print(parsed)
            if not parsed:
                continue
            try:
                act = json_action.JSONAction(**parsed)
                self.env.execute_action(act)
                time.sleep(self.wait_after_action_seconds)
            except Exception:
                # continue
                print("Failed to execute action:", parsed)
        if "terminate" in response or self.repeat_time == 3:
            return base_agent.AgentInteractionResult(
                True, {"operation": op_text, "response": response}
            )
        return base_agent.AgentInteractionResult(
            False, {"operation": op_text, "response": response}
        )

    def get_point_from_description(
        self,
        image: np.ndarray,
        description: str,
    ) -> tuple[int, int]:
        def format_openai_template(description: str, base64_image):
            return [
                {"role": "system", "content": android_system_prompt_grounding},
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_image}"
                            },
                        },
                        {"type": "text", "text": description},
                    ],
                },
            ]

        img = Image.fromarray(image)

        new_width = 1080
        new_height = 2340
        width, height = img.size

        print(width, height)

        img_resized = img.resize((new_width, new_height))

        if img_resized.mode == "RGBA":
            img_resized = img_resized.convert("RGB")

        img_byte_arr = io.BytesIO()
        img_resized.save(img_byte_arr, format="JPEG")
        image_bytes = img_byte_arr.getvalue()

        base64_image = base64.b64encode(image_bytes).decode("utf-8")

        messages = format_openai_template(description, base64_image)

        completion = self.model_client.chat.completions.create(
            model=self.model_name, messages=messages, temperature=0
        )

        response_text = completion.choices[0].message.content
        print(response_text)
        x_ratio, y_ratio = action_coord(response_text)
        print(f"x_ratio: {x_ratio}, y_ratio: {y_ratio}")

        x_coord = round(x_ratio * width)
        y_coord = round(y_ratio * height)

        return (x_coord, y_coord)

    def set_task_guidelines(self, task_guidelines: list[str]) -> None:
        self.additional_guidelines = task_guidelines

    def reset(self, go_home_on_reset: bool = False):
        super().reset(go_home_on_reset)
        self.env.hide_automation_ui()
        self.history = []
        self.step_his = ""
        self.turn_number = 0
        self.last_action = None
        self.repeat_time = 0

    def step_planner(self, goal: str) -> base_agent.AgentInteractionResult:
        step_data = {
            "raw_screenshot": None,
            "before_screenshot_with_som": None,
            "before_ui_elements": [],
            "after_screenshot_with_som": None,
            "action_prompt": None,
            "action_output": None,
            "action_output_json": None,
            "action_reason": None,
            "action_raw_response": None,
            "summary_prompt": None,
            "summary": None,
            "summary_raw_response": None,
        }
        print("----------step " + str(len(self.history) + 1))

        state = self.get_post_transition_state()
        step_data["raw_screenshot"] = state.pixels.copy()
        before_screenshot = state.pixels.copy()
        step_data["before_screenshot_with_som"] = before_screenshot.copy()

        action_prompt = _action_selection_prompt_locate(
            goal,
            [
                "Step " + str(i + 1) + "- " + step_info["summary"]
                for i, step_info in enumerate(self.history)
            ],
            None,
            self.additional_guidelines,
        )
        step_data["action_prompt"] = action_prompt
        action_output, is_safe, raw_response = self.llm.predict_mm(
            action_prompt,
            [
                step_data["raw_screenshot"],
            ],
        )

        if is_safe == False:
            action_output = f"""Reason: {m3a_utils.TRIGGER_SAFETY_CLASSIFIER}
Action: {{"action_type": "status", "goal_status": "infeasible"}}"""

        if not raw_response:
            raise RuntimeError("Error calling LLM in action selection phase.")
        step_data["action_output"] = action_output
        step_data["action_raw_response"] = raw_response

        reason, action = m3a_utils.parse_reason_action_output(action_output)

        if (not reason) or (not action):
            print("Action prompt output is not in the correct format.")
            step_data["summary"] = (
                "Output for action selection is not in the correct format, so no"
                " action is performed."
            )
            self.history.append(step_data)

            return base_agent.AgentInteractionResult(
                False,
                step_data,
            )
        self.step_his += f"Step {self.turn_number}: {action}\n"
        print("Action: " + action)
        print("Reason: " + reason)
        step_data["action_reason"] = reason
        import traceback

        try:
            converted_action = json_action.JSONAction(
                **agent_utils.extract_json(action),
            )
            step_data["action_output_json"] = converted_action

            if converted_action.element:
                converted_action.x, converted_action.y = (
                    self.get_point_from_description(
                        step_data["raw_screenshot"], converted_action.element
                    )
                )

        except Exception as e:
            print("Failed to convert the output to a valid action.")
            print(traceback.print_exc())
            print(str(e))
            step_data["summary"] = (
                "Can not parse the output to a valid action. Please make sure to pick"
                " the action from the list with required parameters (if any) in the"
                " correct JSON format!"
            )
            self.history.append(step_data)

            return base_agent.AgentInteractionResult(
                False,
                step_data,
            )
        if converted_action.action_type == "status":
            if converted_action.goal_status == "infeasible":
                print("Agent stopped since it thinks mission impossible.")
            step_data["summary"] = "Agent thinks the request has been completed."
            self.history.append(step_data)
            return base_agent.AgentInteractionResult(
                True,
                step_data,
            )

        if converted_action.action_type == "answer":
            print("Agent answered with: " + converted_action.text)

        try:
            self.env.execute_action(converted_action)
        except Exception as e:
            print("Failed to execute action.")
            print(str(e))
            step_data["summary"] = (
                "Can not execute the action, make sure to select the action with"
                " the required parameters (if any) in the correct JSON format!"
            )
            return base_agent.AgentInteractionResult(
                False,
                step_data,
            )

        time.sleep(self.wait_after_action_seconds)

        state = self.env.get_state(wait_to_stabilize=False)

        after_screenshot = state.pixels.copy()

        if converted_action.x:
            m3a_utils.add_ui_element_dot(
                before_screenshot,
                target_element=(
                    [round(converted_action.x), round(converted_action.y)]
                    if converted_action.x
                    else None
                ),
            )

        step_data["before_screenshot_with_som"] = before_screenshot.copy()
        m3a_utils.add_screenshot_label(after_screenshot, "after")
        step_data["after_screenshot_with_som"] = after_screenshot.copy()

        summary_prompt = _summarize_prompt(
            action,
            reason,
            goal,
            None,
            None,
        )
        summary, is_safe, raw_response = self.llm.predict_mm(
            summary_prompt,
            [
                before_screenshot,
                after_screenshot,
            ],
        )

        if is_safe == False:
            summary = """Summary triggered LLM safety classifier."""

        if not raw_response:
            print(
                "Error calling LLM in summarization phase. This should not happen: "
                f"{summary}"
            )
            step_data["summary"] = (
                "Some error occurred calling LLM during summarization phase: %s"
                % summary
            )
            self.history.append(step_data)
            return base_agent.AgentInteractionResult(
                False,
                step_data,
            )

        step_data["summary_prompt"] = summary_prompt
        step_data["summary"] = f"Action selected: {action}. {summary}"
        print("Summary: " + summary)
        step_data["summary_raw_response"] = raw_response

        self.history.append(step_data)
        return base_agent.AgentInteractionResult(
            False,
            step_data,
        )

    @staticmethod
    def _to_base64_png(image: np.ndarray) -> str:
        import base64
        from io import BytesIO
        from PIL import Image as PILImage

        buf = BytesIO()
        PILImage.fromarray(image).save(buf, format="PNG")
        return f"data:image/png;base64,{base64.b64encode(buf.getvalue()).decode()}"


class QwenVL(base_agent.EnvironmentInteractingAgent):
    def __init__(
        self,
        env: interface.AsyncEnv,
        llm: infer.MultimodalLlmWrapper,
        name: str = "M3A",
        wait_after_action_seconds: float = 2.0,
        model_address="http://10.140.60.2:10020/",
        model_api_key="fake",
        model_name="",
        mode="agent",
    ):
        super().__init__(env, name)
        self.llm = llm
        self.history = []
        self.additional_guidelines = None
        self.wait_after_action_seconds = wait_after_action_seconds
        self.grounding_address = model_address
        print(model_address)
        print(f"{model_address}v1")
        self.model_client = OpenAI(base_url=f"{model_address}v1", api_key=model_api_key)
        self.step_his: str = ""
        self.turn_number: int = 0
        self.model_name = model_name
        self.last_action = None
        self.repeat_time = 0
        self.mode = mode  # 'agent' or 'grounder'

    def step(self, instruction: str) -> base_agent.AgentInteractionResult:
        if self.mode == "grounder":
            return self.step_planner(instruction)
        else:
            return self.step_agent(instruction)

    def step_agent(self, instruction: str) -> base_agent.AgentInteractionResult:
        self.turn_number += 1
        state = self.get_post_transition_state()
        screenshot = state.pixels.copy()
        screenshot = screenshot[:, :, ::-1]
        if self.save_dir is not None:
            screenshot_path = os.path.join(
                self.save_dir, f"screenshot_{self.turn_number}.png"
            )
            cv2.imwrite(screenshot_path, screenshot)
            print(f"Screenshot saved to {screenshot_path}")
        height, width = screenshot.shape[:2]

        # system_prompt = internvl2_5_mobile_planning_cot_v1
        system_prompt = android_system_prompt_navigation
        user_prompt = android_user_prompt.format(
            instruction=instruction, actions=self.step_his
        )

        headers = {"Content-Type": "application/json"}
        url = f"{self.grounding_address}v1/chat/completions"
        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {"url": self._to_base64_png(screenshot)},
                        },
                        {"type": "text", "text": user_prompt},
                    ],
                },
            ],
        }
        response = requests.post(url, headers=headers, data=json.dumps(payload))
        response.raise_for_status()
        response = response.json()["choices"][0]["message"]["content"]
        print(response)
        print("=" * 50)
        op_m = re.search(r"<operation>([\s\S]*?)</operation>", response)
        act_m = re.search(r"<action>([\s\S]*?)</action>", response)
        op_text = op_m.group(1).strip() if op_m else ""
        self.step_his += f"Step {self.turn_number}: {op_text}\n"

        if not act_m:
            return base_agent.AgentInteractionResult(
                True, {"summary": "No valid action returned."}
            )
        if self.last_action == act_m.group(1):
            self.repeat_time += 1
        else:
            self.repeat_time = 0
        self.last_action = act_m.group(1)
        cmds = [l for l in act_m.group(1).splitlines() if l.strip()]
        print(cmds)
        for cmd in cmds:
            parsed = qwen_action_transform(
                cmd,
                width,
                height,
                smart_resize_option=True,
                min_pixels=3136,
                max_pixels=2109744,
            )
            print(parsed)
            if not parsed:
                continue
            try:
                act = json_action.JSONAction(**parsed)
                self.env.execute_action(act)
                time.sleep(self.wait_after_action_seconds)
            except Exception:
                print("Failed to execute action:", parsed)
        if "terminate" in response or self.repeat_time == 3:
            return base_agent.AgentInteractionResult(
                True,
                {
                    "operation": op_text,
                    "response": response,
                    "step_history": self.step_his,
                },
            )
        return base_agent.AgentInteractionResult(
            False,
            {"operation": op_text, "response": response, "step_history": self.step_his},
        )

    def get_point_from_description(
        self,
        image: np.ndarray,
        description: str,
    ) -> tuple[int, int]:

        def format_openai_template(description: str, base64_image):
            return [
                {"role": "system", "content": android_system_prompt_grounding},
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_image}"
                            },
                        },
                        {
                            "type": "text",
                            "text": description,
                        },
                    ],
                },
            ]

        img = Image.fromarray(image)

        new_width = 1080
        new_height = 2340
        width, height = img.size

        print(width, height)

        img_resized = img.resize((new_width, new_height))

        if img_resized.mode == "RGBA":
            img_resized = img_resized.convert("RGB")

        img_byte_arr = io.BytesIO()
        img_resized.save(img_byte_arr, format="JPEG")
        image_bytes = img_byte_arr.getvalue()

        base64_image = base64.b64encode(image_bytes).decode("utf-8")

        messages = format_openai_template(description, base64_image)

        headers = {"Content-Type": "application/json"}
        url = f"{self.grounding_address}v1/chat/completions"
        payload = {"model": self.model_name, "messages": messages}
        response = requests.post(url, headers=headers, data=json.dumps(payload))
        response.raise_for_status()
        response_text = response.json()["choices"][0]["message"]["content"]
        print(response_text)
        x_ratio, y_ratio = action_coord(response_text)
        print(f"x_ratio: {x_ratio}, y_ratio: {y_ratio}")
        resized_height, resized_width = smart_resize(
            height, width, min_pixels=3136, max_pixels=2109744
        )
        x_coord = round(x_ratio / resized_width * width)
        y_coord = round(y_ratio / resized_height * height)

        return (x_coord, y_coord)

    def set_task_guidelines(self, task_guidelines: list[str]) -> None:
        self.additional_guidelines = task_guidelines

    def reset(self, go_home_on_reset: bool = False):
        super().reset(go_home_on_reset)
        self.env.hide_automation_ui()
        self.history = []
        self.step_his = ""
        self.turn_number = 0
        self.last_action = None
        self.repeat_time = 0

    def step_planner(self, goal: str) -> base_agent.AgentInteractionResult:
        step_data = {
            "raw_screenshot": None,
            "before_screenshot_with_som": None,
            "before_ui_elements": [],
            "after_screenshot_with_som": None,
            "action_prompt": None,
            "action_output": None,
            "action_output_json": None,
            "action_reason": None,
            "action_raw_response": None,
            "summary_prompt": None,
            "summary": None,
            "summary_raw_response": None,
            "response": None,
            "step_history": None,
        }
        print("----------step " + str(len(self.history) + 1))

        state = self.get_post_transition_state()
        step_data["raw_screenshot"] = state.pixels.copy()
        before_screenshot = state.pixels.copy()
        step_data["before_screenshot_with_som"] = before_screenshot.copy()

        action_prompt = _action_selection_prompt_locate(
            goal,
            [
                "Step " + str(i + 1) + "- " + step_info["summary"]
                for i, step_info in enumerate(self.history)
            ],
            None,
            self.additional_guidelines,
        )
        step_data["action_prompt"] = action_prompt
        action_output, is_safe, raw_response = self.llm.predict_mm(
            action_prompt,
            [
                step_data["raw_screenshot"],
            ],
        )

        if is_safe == False:
            action_output = f"""Reason: {m3a_utils.TRIGGER_SAFETY_CLASSIFIER}
Action: {{"action_type": "status", "goal_status": "infeasible"}}"""

        if not raw_response:
            raise RuntimeError("Error calling LLM in action selection phase.")
        step_data["action_output"] = action_output
        step_data["action_raw_response"] = raw_response

        reason, action = m3a_utils.parse_reason_action_output(action_output)
        if (not reason) or (not action):
            print("Action prompt output is not in the correct format.")
            step_data["summary"] = (
                "Output for action selection is not in the correct format, so no"
                " action is performed."
            )
            self.history.append(step_data)

            return base_agent.AgentInteractionResult(
                False,
                step_data,
            )
        self.step_his += f"Step {self.turn_number}: {action}\n"
        step_data["step_history"] = self.step_his
        step_data["response"] = action_output
        print("Action: " + action)
        print("Reason: " + reason)
        step_data["action_reason"] = reason
        import traceback

        try:
            converted_action = json_action.JSONAction(
                **agent_utils.extract_json(action),
            )
            step_data["action_output_json"] = converted_action

            if converted_action.element:
                converted_action.x, converted_action.y = (
                    self.get_point_from_description(
                        step_data["raw_screenshot"], converted_action.element
                    )
                )

        except Exception as e:
            print("Failed to convert the output to a valid action.")
            print(traceback.print_exc())
            print(str(e))
            step_data["summary"] = (
                "Can not parse the output to a valid action. Please make sure to pick"
                " the action from the list with required parameters (if any) in the"
                " correct JSON format!"
            )
            self.history.append(step_data)

            return base_agent.AgentInteractionResult(
                False,
                step_data,
            )
        if converted_action.action_type == "status":
            if converted_action.goal_status == "infeasible":
                print("Agent stopped since it thinks mission impossible.")
            step_data["summary"] = "Agent thinks the request has been completed."
            self.history.append(step_data)
            return base_agent.AgentInteractionResult(
                True,
                step_data,
            )

        if converted_action.action_type == "answer":
            print("Agent answered with: " + converted_action.text)

        try:
            self.env.execute_action(converted_action)
        except Exception as e:
            print("Failed to execute action.")
            print(str(e))
            step_data["summary"] = (
                "Can not execute the action, make sure to select the action with"
                " the required parameters (if any) in the correct JSON format!"
            )
            return base_agent.AgentInteractionResult(
                False,
                step_data,
            )

        time.sleep(self.wait_after_action_seconds)

        state = self.env.get_state(wait_to_stabilize=False)

        after_screenshot = state.pixels.copy()
        if converted_action.x:
            m3a_utils.add_ui_element_dot(
                before_screenshot,
                target_element=(
                    [round(converted_action.x), round(converted_action.y)]
                    if converted_action.x
                    else None
                ),
            )

        step_data["before_screenshot_with_som"] = before_screenshot.copy()
        m3a_utils.add_screenshot_label(after_screenshot, "after")
        step_data["after_screenshot_with_som"] = after_screenshot.copy()

        summary_prompt = _summarize_prompt(
            action,
            reason,
            goal,
            None,
            None,
        )
        summary, is_safe, raw_response = self.llm.predict_mm(
            summary_prompt,
            [
                before_screenshot,
                after_screenshot,
            ],
        )

        if is_safe == False:
            summary = """Summary triggered LLM safety classifier."""

        if not raw_response:
            print(
                "Error calling LLM in summarization phase. This should not happen: "
                f"{summary}"
            )
            step_data["summary"] = (
                "Some error occurred calling LLM during summarization phase: %s"
                % summary
            )
            self.history.append(step_data)
            return base_agent.AgentInteractionResult(
                False,
                step_data,
            )

        step_data["summary_prompt"] = summary_prompt
        step_data["summary"] = f"Action selected: {action}. {summary}"
        print("Summary: " + summary)
        step_data["summary_raw_response"] = raw_response

        self.history.append(step_data)
        return base_agent.AgentInteractionResult(
            False,
            step_data,
        )

    @staticmethod
    def _to_base64_png(image: np.ndarray) -> str:
        import base64
        from io import BytesIO
        from PIL import Image as PILImage

        buf = BytesIO()
        PILImage.fromarray(image).save(buf, format="PNG")
        return f"data:image/png;base64,{base64.b64encode(buf.getvalue()).decode()}"


def _extract_action_text_qwen3vl(block: str) -> str:
    """Extracts the 'Action:' line from Qwen3VL text output for step history (does not affect execution)."""
    m = re.search(r"Action:\s*(.+?)(?:\n<tool_call>|$)", block, flags=re.S)
    if not m:
        return ""
    text = m.group(1).strip()
    # Some models wrap Action: "..." with quotes.
    if text.startswith('"') and text.endswith('"'):
        text = text[1:-1]
    return text.replace("\n", " ")


def _parse_tool_call_json(block: str) -> dict[str, Any] | None:
    """Parse JSON inside <tool_call>...</tool_call>."""
    m = re.search(r"<tool_call>\s*([\s\S]*?)\s*</tool_call>", block)
    if not m:
        return None
    payload = m.group(1).strip()
    try:
        return json.loads(payload)
    except Exception:
        return None


class Qwen3VL(base_agent.EnvironmentInteractingAgent):
    """Android GUI Agent based on Qwen3VL tool-call output (for AndroidWorld eval).

    - Input: Screenshot + instruction + history
    - Output: <tool_call>{...}</tool_call>
    - Execution: Map to JSONAction by qwen3vl_action_transform(...)
    """

    def __init__(
        self,
        env: interface.AsyncEnv,
        llm: infer.MultimodalLlmWrapper,
        name: str = "Qwen3VL",
        wait_after_action_seconds: float = 2.0,
        model_base_url: str = "http://127.0.0.1:8000/v1",
        model_api_key: str = "EMPTY",
        model_name: str = "",
        extra_headers: dict[str, str] | None = None,
    ):
        super().__init__(env, name)
        self.llm = llm
        self.wait_after_action_seconds = wait_after_action_seconds
        self.model_name = model_name
        self.client = OpenAI(
            api_key=model_api_key,
            base_url=model_base_url,
            default_headers=extra_headers,
        )
        self.step_his: str = ""
        self.turn_number: int = 0
        # Used to detect repeated actions (avoid infinite loops)
        self.last_action: str | None = None
        self.repeat_time: int = 0

    def reset(self, go_home_on_reset: bool = False):
        super().reset(go_home_on_reset)
        self.env.hide_automation_ui()
        self.step_his = ""
        self.turn_number = 0
        self.last_action = None
        self.repeat_time = 0

    @staticmethod
    def _to_base64_png(image: np.ndarray) -> str:
        import base64
        from io import BytesIO
        from PIL import Image as PILImage
        buf = BytesIO()
        PILImage.fromarray(image).save(buf, format='PNG')
        return f"data:image/png;base64,{base64.b64encode(buf.getvalue()).decode()}"
        
    def step(self, instruction: str) -> base_agent.AgentInteractionResult:
        self.turn_number += 1

        state = self.get_post_transition_state()
        screenshot = state.pixels.copy()
        # To be consistent with other agents in this file: BGR->RGB (for saving/encoding)
        screenshot = screenshot[:, :, ::-1]
        height, width = screenshot.shape[:2]

        system_prompt = QWEN3VL_SYSTEM_PROMPT
        user_prompt = QWEN3VL_USER_PROMPT.format(
            instruction=instruction, history=self.step_his
        )

        messages = [
            {
                "role": "system",
                "content": [{"type": "text", "text": system_prompt}],
            },
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": user_prompt},
                    {"type": "image_url", "image_url": {"url": self._to_base64_png(screenshot)}},
                ],
            },
        ]

        completion = self.client.chat.completions.create(
            model=self.model_name,
            messages=messages,
            temperature=0,
        )
        response = completion.choices[0].message.content or ""
        print(response)
        print("=" * 50)

        tool_call = _parse_tool_call_json(response)
        if not tool_call:
            return base_agent.AgentInteractionResult(
                True, {"summary": "No <tool_call> JSON found in model output.", "response": response}
            )

        op_text = _extract_action_text_qwen3vl(response)
        if op_text:
            self.step_his += f"Step {self.turn_number}: {op_text}; "

        # Compatible: tool_call may look like {"name":"mobile_use","arguments":{...}}
        args = tool_call.get("arguments", {}) if isinstance(tool_call, dict) else {}
        action_name = args.get("action", "")
        try:
            parsed = qwen3vl_action_transform(action_name, args, width, height)
            print(parsed)
        except Exception as e:
            return base_agent.AgentInteractionResult(
                True,
                {
                    "summary": f"Failed to transform tool-call into action: {e}",
                    "response": response,
                    "tool_call": tool_call,
                },
            )

        # Record last_action + repeat_time (previous code had these fields but not working)
        # Here, use the tool-call's arguments as the "action signature", which is more robust than checking 'terminate' in a string.
        try:
            action_sig = json.dumps(args, ensure_ascii=False, sort_keys=True)
        except Exception:
            action_sig = str(args)
        if self.last_action == action_sig:
            self.repeat_time += 1
        else:
            self.repeat_time = 0
        self.last_action = action_sig

        try:
            act = json_action.JSONAction(**parsed)
            self.env.execute_action(act)
            time.sleep(self.wait_after_action_seconds)
        except Exception:
            # continue
            print("Failed to execute action:", parsed)

        if parsed.get("action_type") == "status":
            return base_agent.AgentInteractionResult(
                True, {"response": response, "step_history": self.step_his, "parsed": parsed}
            )

        # If repeated actions reach the threshold: terminate immediately to avoid deadlock in evaluation
        if self.repeat_time >= 3:
            return base_agent.AgentInteractionResult(
                True,
                {
                    "summary": "Terminated due to repeated identical actions.",
                    "response": response,
                    "step_history": self.step_his,
                    "parsed": parsed,
                    "repeat_time": self.repeat_time,
                },
            )

        return base_agent.AgentInteractionResult(
            False, {"response": response, "step_history": self.step_his, "parsed": parsed}
        )
