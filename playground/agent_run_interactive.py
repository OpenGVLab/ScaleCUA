import argparse
import datetime
import logging
import os
import sys
import time
from utils.utils import draw_tag_on_image
from envs import *
from datetime import datetime
from PIL import Image
from datetime import datetime
import yaml, json
from agents.framework_agent import AgenticWorkflow
from agents.native_agent import NativeAgent
from dotenv import load_dotenv

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

ENVS = {
    "web": WebEnv,
    "ubuntu_web": UbuntuWebEnv,
    "android": AndroidEnv,
    "ubuntu": UbuntuEnv,
}


def create_log(path, datetime_str):

    logger.handlers.clear()

    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setLevel(logging.INFO)
    formatter = logging.Formatter(
        fmt="\x1b[1;33m[%(asctime)s \x1b[31m%(levelname)s \x1b[32m%(module)s/%(lineno)d-%(processName)s\x1b[1;33m] \x1b[0m%(message)s"
    )
    stdout_handler.setFormatter(formatter)
    logger.addHandler(stdout_handler)

    file_handler = logging.FileHandler(
        os.path.join(path, "normal-{:}.log".format(datetime_str)), encoding="utf-8"
    )
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)

    logger.addHandler(file_handler)


def run_agent(agent, instruction: str, env: None, root_folder: None, **task_kwargs):
    os.makedirs(root_folder, exist_ok=True)
    folder_name = datetime.now().strftime("%Y%m%d_%H%M%S")
    save_folder = os.path.join(root_folder, folder_name)
    os.makedirs(save_folder, exist_ok=True)
    create_log(save_folder, folder_name)
    logger.info(f"Instruction: {instruction}")

    env.start_recording()
    for idx in range(20):

        obs = env.get_obs()
        with open(os.path.join(save_folder, f"step-{idx}.png"), "wb") as image_save:
            image_save.write(obs["screenshot"])
        if idx == 21:
            info, code = None, [
                {
                    "name": "terminate",
                    "parameters": {"status": "failure"},
                }
            ]
        else:
            info, code = agent.predict(
                instruction=instruction, observation=obs, env=env
            )

        draw_tag_on_image(
            code[0],
            obs["screenshot"],
            os.path.join(save_folder, f"draw_step-{idx}.png"),
        )
        with open(
            os.path.join(save_folder, "action.jsonl"), "a", encoding="utf-8"
        ) as action_save:
            json.dump(code, action_save, ensure_ascii=False)
            action_save.write("\n")

        if code[0]["name"] == "terminate":
            print("Task End!")
            break

        if code[0]["name"] == "wait":
            time.sleep(5)
            continue

        else:
            time.sleep(1.0)
            print("Predict action:", code)

            env.step(code)
            time.sleep(2.0)

    env.end_recording(os.path.join(save_folder, "recording.mp4"))

    return 0


def main():
    parser = argparse.ArgumentParser(
        description="Run GraphSearchAgent with specified model."
    )
    parser.add_argument(
        "--env_config_path",
        type=str,
        default="config/env/ubuntu.yaml",
        help="Specify the env",
    )
    parser.add_argument(
        "--agent_config_path",
        type=str,
        default="config/agent/test_ours_grounder.yaml",
        help="Specify the model to use (e.g., gpt-4o)",
    )
    parser.add_argument(
        "--platform",
        type=str,
        default="ubuntu",
        help="Specify the platform",
    )

    args = parser.parse_args()

    with open(args.env_config_path, "r") as f:
        env_config = yaml.safe_load(f)
    env = ENVS[args.platform](**env_config)
    screen_width, screen_height = env.screen_size

    with open(args.agent_config_path, "r") as f:
        agent_config = yaml.safe_load(f)

    # planner + grounder
    if "ui_grounding_model" in agent_config:
        engine_params_for_ui_grounding = agent_config["ui_grounding_model"]
        engine_params_for_planner = agent_config["planner_model"]

        if (
            "grounding_height" in engine_params_for_ui_grounding
            and engine_params_for_ui_grounding["grounding_height"] is None
        ):
            engine_params_for_ui_grounding["grounding_height"] = (
                screen_height
                * engine_params_for_ui_grounding["grounding_width"]
                / screen_width
            )

        agent = AgenticWorkflow(
            engine_params_for_planner,
            engine_params_for_ui_grounding,
            args.platform,
        )

    else:
        engine_params_for_planner = agent_config["planner_model"]
        agent = NativeAgent(
            engine_params_for_planner,
            grounding_width=agent_config["planner_model"]["grounding_width"],
            grounding_height=agent_config["planner_model"]["grounding_height"],
            prompt_template=agent_config["planner_model"]["prompt_template"],
            platform=args.platform,
            observation_type="vision",
        )

    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    task_kwargs = {}
    while True:
        query = input("Query: ")

        # Web Platform must start recording before reset
        if args.platform == "web":
            env.start_recording()

        env.reset(**task_kwargs)
        agent.reset()
        task_config = {}
        # Run the agent on your own device
        _ = run_agent(agent, query, env, f"interative/{timestamp}", **task_config)

        response = input("Would you like to provide another query? (y/n): ")
        if response.lower() != "y":
            break

    env.exit()


if __name__ == "__main__":
    load_dotenv()
    main()
