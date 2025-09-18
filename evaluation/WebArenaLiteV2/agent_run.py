import argparse
import copy
import logging
import multiprocessing
import os
import sys
from collections import defaultdict
from dotenv import load_dotenv

from agents.agentic_workflow.scalecua_agentic_workflow import OpenCUAAgenticWorkflow
from agents.native_agent.scalecua_native_agent import OpenCUANativeAgent
from envs.web.ubuntu_web_env import VMUbuntuWebEnv
from envs.web.web_env import WebEnv
from datetime import datetime
import yaml, json

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)
import traceback
from utils.misc import *


def create_log(path, datetime_str):
    """
    Configure logging with handlers for both console output and file storage.

    Args:
        path: Directory path for log files
        datetime_str: Timestamp string for log file names
    """
    # Clear all existing handlers
    logger.handlers.clear()

    # Add StreamHandler for console output
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setLevel(logging.INFO)
    formatter = logging.Formatter(
        fmt="\x1b[1;33m[%(asctime)s \x1b[31m%(levelname)s \x1b[32m%(module)s/%(lineno)d-%(processName)s\x1b[1;33m] \x1b[0m%(message)s"
    )
    stdout_handler.setFormatter(formatter)
    logger.addHandler(stdout_handler)

    # File handlers are commented out but kept for reference
    # file_handler = logging.FileHandler(
    #     os.path.join(path, "normal-{:}.log".format(datetime_str)), encoding="utf-8"
    # )
    # # debug_handler = logging.FileHandler(
    # #     os.path.join(path, "debug-{:}.log".format(datetime_str)), encoding="utf-8"
    # # )
    # sdebug_handler = logging.FileHandler(
    #     os.path.join(path, "sdebug-{:}.log".format(datetime_str)), encoding="utf-8"
    # )
    #
    # file_handler.setLevel(logging.INFO)
    # # debug_handler.setLevel(logging.DEBUG)
    # sdebug_handler.setLevel(logging.DEBUG)
    #
    # file_handler.setFormatter(formatter)
    # # debug_handler.setFormatter(formatter)
    # sdebug_handler.setFormatter(formatter)
    #
    # sdebug_handler.addFilter(logging.Filter("desktopenv"))
    #
    # logger.addHandler(file_handler)
    # # logger.addHandler(debug_handler)
    # logger.addHandler(sdebug_handler)


def run_agent(agent, instruction: str, env, root_folder, max_steps=15, **task_kwargs):
    """
    Execute agent actions in the environment based on the given instruction.

    Args:
        agent: The agent that will execute actions
        instruction: The task instruction for the agent
        env: The environment where actions will be executed
        root_folder: Base directory for storing results
        max_steps: Maximum number of steps the agent can execute
        **task_kwargs: Additional task configuration parameters

    Returns:
        float: Evaluation metric (score) for the task
    """
    os.makedirs(root_folder, exist_ok=True)

    task_id = task_kwargs["task_config"]["example_id"].split(".")[0]
    save_folder = os.path.join(root_folder, task_id)

    # Checkpoint recovery mechanism
    if os.path.exists(os.path.join(save_folder, "result.json")):
        with open(os.path.join(save_folder, "result.json")) as f:
            result = json.load(f)
        if "metric" in result:
            return result["metric"]

    os.makedirs(save_folder, exist_ok=True)
    os.makedirs(
        os.path.join(save_folder, "trajectory"), exist_ok=True
    )  # For saving screenshots

    idx = 0
    metric = 0

    result = copy.deepcopy(RESULT_TEMPLATE)
    result["task_id"] = task_id
    result["task"] = instruction

    collected_data = defaultdict(list)

    evaluate_actions = []

    for idx in range(max_steps):
        obs = env.get_obs()

        with open(
            os.path.join(save_folder, "trajectory", f"{idx}.png"), "wb"
        ) as image_save:
            image_save.write(obs["screenshot"])

        # Predict current step action
        info, code = agent.predict(instruction=instruction, observation=obs)

        for key, value in info.items():
            collected_data[key].append(value)

        evaluate_actions.extend(code)

        if "x" in code[0]["parameters"] and "y" in code[0]["parameters"]:
            draw_xy(
                os.path.join(save_folder, "trajectory", f"{idx}.png"),
                code[0]["parameters"]["x"],
                code[0]["parameters"]["y"],
                os.path.join(save_folder, "trajectory", f"{idx}_draw.png"),
            )

        # Execute the current step
        env.step(code)

        if code[0]["name"] == "terminate":
            break

    for key, value_list in collected_data.items():
        result[key] = value_list

    result["steps"] = idx + 1
    with open(os.path.join(save_folder, "result.json"), "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=4)

    # Evaluation
    evaluate_kwargs = {
        "actions": evaluate_actions,
        "benchmark": task_kwargs["benchmark"],
    }

    if task_kwargs["task_config"] is not None:
        metric = env.evaluate(**evaluate_kwargs)

    return metric


def init_env_and_agent(args):
    """
    Initialize the environment and agent based on configuration.

    Args:
        args: Command line arguments containing configuration paths

    Returns:
        tuple: (env, agent) - initialized environment and agent
    """
    with open(args.env_config_path, "r") as f:
        env_config = yaml.safe_load(f)

    if args.platform == "web":
        env = WebEnv(**env_config)
    elif args.platform == "ubuntu_web":
        env = VMUbuntuWebEnv(**env_config)
    else:
        print(f"Not support for {args.platform}")

    # Load agent configuration
    with open(args.agent_config_path, "r") as f:
        agent_config = yaml.safe_load(f)

    screen_width, screen_height = env.screen_size

    # Initialize agent
    if "ui_grounding_model" not in agent_config:
        engine_params_for_planner = agent_config["planner_model"]
        agent = OpenCUANativeAgent(
            engine_params_for_planner,  # Planner Model
            platform=args.platform,
            width=screen_width,
            height=screen_height,
        )
    else:
        engine_params_for_planner = agent_config["planner_model"]
        engine_params_for_ui_grounding = agent_config["ui_grounding_model"]
        agent = OpenCUAAgenticWorkflow(
            engine_params_for_planner,
            engine_params_for_ui_grounding,
            args.platform,
        )

    return env, agent


def worker(args, worker_id):
    """
    Worker process function for parallel task execution.

    Args:
        args: Command line arguments
        worker_id: Unique identifier for this worker

    Returns:
        list: Results from tasks processed by this worker
    """
    env, agent = init_env_and_agent(args)

    task_files = [
        os.path.join(args.task_config_path, f)
        for f in os.listdir(args.task_config_path)
        if os.path.isfile(os.path.join(args.task_config_path, f))
    ]
    task_files = [
        task_file
        for i, task_file in enumerate(task_files)
        if i % args.num_workers == worker_id
    ]
    print(f"{multiprocessing.current_process().pid} is processing {task_files}")

    results = []
    for i, task_file in enumerate(task_files):

        with open(task_file, "r", encoding="utf-8") as f:
            task_config = json.load(f)
            query = task_config.pop("query")
            agent.reset()
            print(f"Execute Task: {task_config}. Query: {query}")

            # Skip task if starting page fails to load
            try:
                env.reset(**task_config)
                metric = run_agent(
                    agent,
                    query,
                    env,
                    os.path.join("results", args.exp_name),
                    max_steps=args.max_steps,
                    **task_config,
                )
            except Exception as e:
                print(f"Error processing task {task_file}: {traceback.print_exc()}")
                metric = 0

        if metric is not None:
            print(f"Task completed with metric: {metric}")
            results.append(
                {
                    "id": i,
                    "metric": metric,
                    "query": query,
                    "task_config": task_config,
                    "save_folder": f"results/{args.exp_name}/{task_config['task_config']['example_id'].split('.')[0]}",
                }
            )

    env.exit()
    return results


def multi_processes(args):
    """
    Manage multiple worker processes for parallel task execution.

    Args:
        args: Command line arguments

    Returns:
        list: Combined results from all worker processes
    """
    worker_args = [(args, worker_id) for worker_id in range(args.num_workers)]
    if args.num_workers > 1:
        with multiprocessing.Pool(processes=args.num_workers) as pool:
            combine_test_result_list = pool.starmap(worker, worker_args)
            test_result_list = [
                item for sublist in combine_test_result_list for item in sublist
            ]
    else:
        test_result_list = worker(*worker_args[0])

    return test_result_list


def parse_args():
    """
    Parse command line arguments.

    Returns:
        argparse.Namespace: Parsed command line arguments
    """
    parser = argparse.ArgumentParser(description="Run Online Web Evaluation.")
    parser.add_argument(
        "--mode",
        type=str,
        default="test",
        help="test / demo",
    )
    parser.add_argument(
        "--env_config_path",
        type=str,
        default="config/envs/web.yaml",
        help="Specify the env",
    )
    parser.add_argument(
        "--agent_config_path",
        type=str,
        default="config/agent/scalecua_native_agent.yaml",
        help="Specify the model to use (e.g., gpt-4o)",
    )
    parser.add_argument(
        "--task_config_path",
        type=str,
        default="tasks",
        help="Specify the benchmark task folder to test.",
    )
    parser.add_argument(
        "--num_workers",
        type=int,
        default=1,
        help="Test with process worker nums",
    )
    parser.add_argument(
        "--platform",
        type=str,
        default="web",
        help="Specify the platform, web/ubuntu_web",
    )

    parser.add_argument(
        "--exp_name",
        type=str,
        default="default",
        help="Experiment name, the sub dir to save results",
    )

    parser.add_argument(
        "--max_steps",
        type=int,
        default=15,
        help="Max steps the agent can execute, default is 15",
    )
    return parser.parse_args()


def demo(args):
    """
    Run the agent in interactive demo mode.

    Args:
        args: Command line arguments
    """
    env, agent = init_env_and_agent(args)
    agent.reset()

    while True:
        query = input("Please enter your task (enter q to quit): ")
        if query.lower() == "q":
            print("Program exited")
            break

        url = input("Please enter your starting URL: ")

        # Get current time and format as month-day-hour-minute-second
        current_time = datetime.now().strftime("%m%d%H%M%S")

        task_config = {
            "url": url,
            "benchmark": "demo",
            "task_config": {"example_id": f"{current_time}.json"},
        }

        try:
            agent.reset()
            env.reset(**task_config)
            run_agent(
                agent,
                query,
                env,
                os.path.join("results", args.exp_name),
                max_steps=args.max_steps,
                **task_config,
            )
        except Exception as e:
            traceback.print_exc()
            print(f"Error processing task: {e}")


def evaluate_results(args, test_result_list):
    """
    Evaluate and summarize test results.

    Args:
        args: Command line arguments
        test_result_list: List of test results to evaluate
    """
    result_path = os.path.join("results", args.exp_name)
    with open(os.path.join(result_path, "results.jsonl"), "a", encoding="utf-8") as f:
        for test_result in test_result_list:
            f.write(json.dumps(test_result, ensure_ascii=False) + "\n")

    with open(os.path.join(result_path, "results.jsonl"), "r", encoding="utf-8") as f:
        lines = f.readlines()
        total_scores = 0
        total_tasks = 0
        for line in lines:
            data = json.loads(line)
            metric = data.get("metric")
            if metric is not None:
                total_scores += metric
                total_tasks += 1
    print(
        f"Total tasks: {total_tasks}, Total scores: {total_scores}, average score: {total_scores / total_tasks if total_tasks > 0 else 0}"
    )


def main():
    """
    Main function to run evaluation or demo mode.
    """
    args = parse_args()
    if args.platform == "ubuntu_web":
        args.num_workers = 1

    if args.mode == "test":
        test_result_list = multi_processes(args)
        evaluate_results(args, test_result_list)

    elif args.mode == "demo":
        demo(args)


if __name__ == "__main__":
    load_dotenv()
    main()
