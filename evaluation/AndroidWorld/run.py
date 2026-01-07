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

"""Run eval suite.

The run.py module is used to run a suite of tasks, with configurable task
combinations, environment setups, and agent configurations. You can run specific
tasks or all tasks in the suite and customize various settings using the
command-line flags.
"""

import os

# ---- Reduce noisy gRPC C++/absl logs (must be set BEFORE importing grpc/android_world) ----
# These messages often look like:
#   I0000 ... fork_posix.cc:71] Other threads are currently calling into gRPC, skipping fork() handlers
# They are usually harmless, but very noisy.
os.environ.setdefault("GRPC_VERBOSITY", "ERROR")
os.environ.setdefault("GRPC_TRACE", "none")
# gRPC uses Abseil logging in C++ in many builds; this env can help reduce INFO logs.
os.environ.setdefault("ABSL_MIN_LOG_LEVEL", "2")  # 0=INFO,1=WARNING,2=ERROR,3=FATAL
# Some environments still honor glog.
os.environ.setdefault("GLOG_minloglevel", "2")

from collections.abc import Sequence
import concurrent.futures
from absl import app
from absl import flags
from absl import logging
from android_world import checkpointer as checkpointer_lib
from android_world import registry
from android_world import suite_utils
from android_world.agents import base_agent
from android_world.agents import human_agent
from android_world.agents import infer
from android_world.agents import m3a
from android_world.agents import random_agent
from android_world.agents import seeact
from android_world.agents import t3a
from android_world.agents import seeact_v
from android_world.env import env_launcher
from android_world.env import interface

logging.set_verbosity(logging.WARNING)


def _find_adb_directory() -> str:
    """Returns the directory where adb is located."""
    potential_paths = [
        os.path.expanduser("~/Library/Android/sdk/platform-tools/adb"),
        os.path.expanduser("~/Android/Sdk/platform-tools/adb"),
        os.path.expanduser("~/android-sdk/platform-tools/adb"),
    ]
    for path in potential_paths:
        if os.path.isfile(path):
            return path
    raise EnvironmentError(
        "adb not found in the common Android SDK paths. Please install Android"
        " SDK and ensure adb is in one of the expected directories. If it's"
        " already installed, point to the installed location."
    )


_ADB_PATH = flags.DEFINE_string(
    "adb_path",
    _find_adb_directory(),
    "Path to adb. Set if not installed through SDK.",
)
_EMULATOR_SETUP = flags.DEFINE_boolean(
    "perform_emulator_setup",
    False,
    "Whether to perform emulator setup. This must be done once and only once"
    " before running Android World. After an emulator is setup, this flag"
    " should always be False.",
)
_DEVICE_CONSOLE_PORT = flags.DEFINE_integer(
    "console_port",
    5554,
    "The console port of the running Android device. This can usually be"
    " retrieved by looking at the output of `adb devices`. In general, the"
    " first connected device is port 5554, the second is 5556, and"
    " so on.",
)

_DEVICE_GRPC_PORT = flags.DEFINE_integer(
    "grpc_port", 8554, "The gprc_port of android device."
)

_SUITE_FAMILY = flags.DEFINE_enum(
    "suite_family",
    registry.TaskRegistry.ANDROID_WORLD_FAMILY,
    [
        # Families from the paper.
        registry.TaskRegistry.ANDROID_WORLD_FAMILY,
        registry.TaskRegistry.MINIWOB_FAMILY_SUBSET,
        # Other families for more testing.
        registry.TaskRegistry.MINIWOB_FAMILY,
        registry.TaskRegistry.ANDROID_FAMILY,
        registry.TaskRegistry.INFORMATION_RETRIEVAL_FAMILY,
    ],
    "Suite family to run. See registry.py for more information.",
)
_TASK_RANDOM_SEED = flags.DEFINE_integer(
    "task_random_seed", 30, "Random seed for task randomness."
)

_TASKS = flags.DEFINE_list(
    "tasks",
    None,
    "List of specific tasks to run in the given suite family. If None, run all"
    " tasks in the suite family.",
)
_N_TASK_COMBINATIONS = flags.DEFINE_integer(
    "n_task_combinations",
    1,
    "Number of task instances to run for each task template.",
)

_CHECKPOINT_DIR = flags.DEFINE_string(
    "checkpoint_dir",
    "try_1st_run",  # Default checkpoint directory.
    "The directory to save checkpoints and resume evaluation from. If the"
    " directory contains existing checkpoint files, evaluation will resume from"
    " the latest checkpoint. If the directory is empty or does not exist, a new"
    " directory will be created.",
)
_OUTPUT_PATH = flags.DEFINE_string(
    "output_path",
    os.path.expanduser("~/android_world/runs"),
    "The path to save results to if not resuming from a checkpoint is not" " provided.",
)

# Agent specific.
_AGENT_NAME = flags.DEFINE_string("agent_name", "seeact_v", help="Agent name.")

# Qwen3VL (OpenAI-compatible server) specific.
_QWEN3VL_MODEL_BASE_URL = flags.DEFINE_string(
    "qwen3vl_model_base_url",
    "http://127.0.0.1:8000/v1",
    "Qwen3VL OpenAI-compatible base_url, e.g. http://host:port/v1",
)
_QWEN3VL_MODEL_API_KEY = flags.DEFINE_string(
    "qwen3vl_model_api_key",
    "EMPTY",
    "Qwen3VL API key for OpenAI-compatible server (if needed).",
)
_QWEN3VL_MODEL_NAME = flags.DEFINE_string(
    "qwen3vl_model_name",
    "",
    "Model name passed to /v1/chat/completions (depends on your server).",
)

_FIXED_TASK_SEED = flags.DEFINE_boolean(
    "fixed_task_seed",
    False,
    "Whether to use the same task seed when running multiple task combinations"
    " (n_task_combinations > 1).",
)


# MiniWoB is very lightweight and new screens/View Hierarchy load quickly.
_MINIWOB_TRANSITION_PAUSE = 0.2

# Additional guidelines for the MiniWob tasks.
_MINIWOB_ADDITIONAL_GUIDELINES = [
    (
        "This task is running in a mock app, you must stay in this app and"
        " DO NOT use the `navigate_home` action."
    ),
]

_TASK_CLASS = flags.DEFINE_integer(
    "task_class",
    0,
    "If >0, split the full family into 3 equal parts and run only that part (1,2 or 3).",
)


def chunk_list(lst: list, n: int) -> list[list]:
    k, m = divmod(len(lst), n)
    chunks = []
    for i in range(n):
        start = i * k + min(i, m)
        end = (i + 1) * k + min(i + 1, m)
        chunks.append(lst[start:end])
    return chunks


def _get_agent(
    env: interface.AsyncEnv,
    family: str | None = None,
) -> base_agent.EnvironmentInteractingAgent:
    """Gets agent."""
    print("Initializing agent...")
    agent = None
    if _AGENT_NAME.value == "human_agent":
        agent = human_agent.HumanAgent(env)
    elif _AGENT_NAME.value == "random_agent":
        agent = random_agent.RandomAgent(env)
    # Gemini.
    elif _AGENT_NAME.value == "m3a_gemini_gcp":
        agent = m3a.M3A(env, infer.GeminiGcpWrapper(model_name="gemini-1.5-pro-latest"))
    elif _AGENT_NAME.value == "t3a_gemini_gcp":
        agent = t3a.T3A(env, infer.GeminiGcpWrapper(model_name="gemini-1.5-pro-latest"))
    # GPT.
    elif _AGENT_NAME.value == "t3a_gpt4":
        agent = t3a.T3A(env, infer.Gpt4Wrapper("gpt-4-turbo-2024-04-09"))
    elif _AGENT_NAME.value == "m3a_gpt4v":
        agent = m3a.M3A(env, infer.Gpt4Wrapper("gpt-4-turbo-2024-04-09"))
    elif _AGENT_NAME.value == "InternVL":
        agent = seeact_v.InternVL(
            env,
            infer.Gpt4Wrapper("gpt-4o"),
            model_name="gui_v106",
            model_address=" http://10.140.66.61:10016",
        )
    elif _AGENT_NAME.value == "qwenvl":
        agent = seeact_v.QwenVL(
            env,
            infer.Gpt4Wrapper("gpt-4o"),
            model_name="gui_v123",
            model_address=" http://10.140.66.139:10026/",
            mode="Agent",
        )
    elif _AGENT_NAME.value == "qwen3vl":
        agent = seeact_v.Qwen3VL(
            env,
            infer.Gpt4Wrapper("gpt-4o"),
            model_base_url=_QWEN3VL_MODEL_BASE_URL.value,
            model_api_key=_QWEN3VL_MODEL_API_KEY.value,
            model_name=_QWEN3VL_MODEL_NAME.value,
        )

    if not agent:
        raise ValueError(f"Unknown agent: {_AGENT_NAME.value}")

    if (
        agent.name in ["M3A", "T3A", "SeeAct"]
        and family
        and family.startswith("miniwob")
        and hasattr(agent, "set_task_guidelines")
    ):
        agent.set_task_guidelines(_MINIWOB_ADDITIONAL_GUIDELINES)
    agent.name = _AGENT_NAME.value

    return agent


def _main() -> None:
    """Runs eval suite and gets rewards back."""
    env = env_launcher.load_and_setup_env(
        console_port=_DEVICE_CONSOLE_PORT.value,
        emulator_setup=_EMULATOR_SETUP.value,
        adb_path=_ADB_PATH.value,
        grpc_port=_DEVICE_GRPC_PORT.value,
    )
    n_task_combinations = _N_TASK_COMBINATIONS.value
    task_registry = registry.TaskRegistry()

    if _TASK_CLASS.value in (1, 2, 3):
        all_tasks = list(task_registry.get_registry(family=_SUITE_FAMILY.value))
        splits = chunk_list(all_tasks, 3)
        tasks_to_run = splits[_TASK_CLASS.value - 1]
    else:
        tasks_to_run = _TASKS.value

    suite = suite_utils.create_suite(
        task_registry.get_registry(family=_SUITE_FAMILY.value),
        n_task_combinations=n_task_combinations,
        seed=_TASK_RANDOM_SEED.value,
        tasks=tasks_to_run,
        use_identical_params=_FIXED_TASK_SEED.value,
    )
    suite.suite_family = _SUITE_FAMILY.value
    # n_task_combinations = _N_TASK_COMBINATIONS.value
    # task_registry = registry.TaskRegistry()
    # suite = suite_utils.create_suite(
    #     task_registry.get_registry(family=_SUITE_FAMILY.value),
    #     n_task_combinations=n_task_combinations,
    #     seed=_TASK_RANDOM_SEED.value,
    #     tasks=_TASKS.value,
    #     use_identical_params=_FIXED_TASK_SEED.value,
    # )
    # suite.suite_family = _SUITE_FAMILY.value

    agent = _get_agent(env, _SUITE_FAMILY.value)

    if _SUITE_FAMILY.value.startswith("miniwob"):
        # MiniWoB pages change quickly, don't need to wait for screen to stabilize.
        agent.transition_pause = _MINIWOB_TRANSITION_PAUSE
    else:
        agent.transition_pause = None

    if _CHECKPOINT_DIR.value:
        checkpoint_dir = _CHECKPOINT_DIR.value
    else:
        checkpoint_dir = checkpointer_lib.create_run_directory(_OUTPUT_PATH.value)

    print(
        f"Starting eval with agent {_AGENT_NAME.value} and writing to"
        f" {checkpoint_dir}"
    )
    suite_utils.run(
        suite,
        agent,
        checkpointer=checkpointer_lib.IncrementalCheckpointer(checkpoint_dir),
        demo_mode=False,
    )
    print(
        f"Finished running agent {_AGENT_NAME.value} on {_SUITE_FAMILY.value}"
        f" family. Wrote to {checkpoint_dir}."
    )
    env.close()


def main(argv: Sequence[str]) -> None:
    del argv
    _main()


if __name__ == "__main__":
    app.run(main)
