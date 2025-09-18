"""
Script to run end-to-end evaluation on the benchmark.
Utils and basic architecture credit to https://github.com/web-arena-x/webarena/blob/main/run.py.
"""
import argparse
import datetime
import json
import logging
import os
import signal
import shutil
import subprocess
import sys
import time
import traceback
from threading import Event

import psutil
import requests
from tqdm import tqdm

import lib_run_single
from desktop_env.envs.desktop_env import DesktopEnv

# --- Key Configurations (Please modify according to your environment) ---
# 1. Path to the clean, golden snapshot of the VM disk.
CLEAN_SNAPSHOT_DIR = "/golden_storage"
# 2. Path to the active VM disk that QEMU will use. This will be overwritten before each test.
ACTIVE_VM_DIR = "/storage"
# Time in seconds to wait for the VM to boot completely.
VM_BOOT_WAIT_TIME = 30
# The full command to start the VM.
START_COMMAND = ['/usr/bin/tini', '-s', '/run/entry.sh']

# --- Logger Configuration ---
root_logger = logging.getLogger()
root_logger.setLevel(logging.DEBUG)
root_logger.propagate = True
datetime_str: str = datetime.datetime.now().strftime("%Y%m%d@%H%M%S")

# Define a colored log format for better readability in the console.
formatter = logging.Formatter(
    fmt="\x1b[1;33m[%(asctime)s \x1b[31m%(levelname)s \x1b[32m%(module)s/%(lineno)d-%(processName)s\x1b[1;33m] \x1b[0m%(message)s"
)

def setup_logging(args: argparse.Namespace):
    """
    Sets up logging to file and console.

    Creates separate log files for different levels (INFO, DEBUG) and sources.
    - normal-*.log: General INFO logs.
    - debug-*.log: General DEBUG logs.
    - sdebug-*.log: DEBUG logs specifically from the 'desktopenv' logger.
    """
    logging_dir = os.path.join(args.result_dir, "logs")
    os.makedirs(logging_dir, exist_ok=True)

    # File Handlers
    file_handler = logging.FileHandler(os.path.join(logging_dir, f"normal-{args.worker_id}-{datetime_str}.log"), encoding="utf-8")
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)

    debug_handler = logging.FileHandler(os.path.join(logging_dir, f"debug-{args.worker_id}-{datetime_str}.log"), encoding="utf-8")
    debug_handler.setLevel(logging.DEBUG)
    debug_handler.setFormatter(formatter)

    sdebug_handler = logging.FileHandler(os.path.join(logging_dir, f"sdebug-{args.worker_id}-{datetime_str}.log"), encoding="utf-8")
    sdebug_handler.setLevel(logging.DEBUG)
    sdebug_handler.setFormatter(formatter)
    sdebug_handler.addFilter(logging.Filter("desktopenv"))

    # Console Handler
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setLevel(logging.INFO)
    stdout_handler.setFormatter(formatter)
    stdout_handler.addFilter(logging.Filter("desktopenv"))

    # Add handlers to root logger
    root_logger.addHandler(file_handler)
    root_logger.addHandler(debug_handler)
    root_logger.addHandler(stdout_handler)
    root_logger.addHandler(sdebug_handler)

logger = logging.getLogger("desktopenv.experiment")
# --- End Logger Configuration ---

def config() -> argparse.Namespace:
    """Parses command-line arguments for the evaluation script."""
    parser = argparse.ArgumentParser(
        description="Run end-to-end evaluation on the benchmark"
    )

    # --- Environment Settings ---
    parser.add_argument("--path_to_vm", type=str, default=None, help="Path to the VM file.")
    parser.add_argument("--headless", action="store_true", help="Run in a headless environment.")
    parser.add_argument("--action_space", type=str, default="pyautogui", help="The action space for the agent.")
    parser.add_argument("--observation_type", choices=["screenshot", "a11y_tree", "screenshot_a11y_tree", "som"], default="screenshot", help="The type of observation to provide to the agent.")
    parser.add_argument("--screen_width", type=int, default=1280, help="Screen width for the environment.")
    parser.add_argument("--screen_height", type=int, default=800, help="Screen height for the environment.")
    parser.add_argument("--sleep_after_execution", type=float, default=2.0, help="Seconds to sleep after each action.")
    parser.add_argument("--max_steps", type=int, default=50, help="Maximum number of steps per episode.")
    parser.add_argument("--emulator_ip", type=str, default="20.20.20.21", help="IP address of the emulator/VM.")
    parser.add_argument("--a11y_backend", type=str, default="uia", help="Accessibility backend ('uia' or 'win32').")

    # --- Agent & Model Settings ---
    parser.add_argument("--agent_name", type=str, default="navi", help="Name of the agent to use.")
    parser.add_argument("--max_trajectory_length", type=int, default=3, help="Maximum trajectory length for the agent.")
    parser.add_argument("--model", type=str, default="uitars", help="The primary model identifier.")
    parser.add_argument("--model_type", type=str, default="qwen25vl", help="The specific type of the model architecture.")
    parser.add_argument("--infer_mode", type=str, default="qwen25vl_normal", help="Inference mode for the model.")
    parser.add_argument("--prompt_style", type=str, default="qwen25vl_normal", help="Prompting style for the model.")
    parser.add_argument("--input_swap", action="store_true", help="Use copy and paste to input text content.")
    parser.add_argument("--language", type=str, default="English", help="Language for the agent's interaction.")
    parser.add_argument("--max_pixels", type=float, default=16384*28*28, help="Maximum number of pixels for image input.")
    parser.add_argument("--min_pixels", type=float, default=100*28*28, help="Minimum number of pixels for image input.")
    parser.add_argument("--temperature", type=float, default=1.0, help="Sampling temperature for the language model.")
    parser.add_argument("--top_p", type=float, default=0.9, help="Nucleus sampling 'top_p' value.")
    parser.add_argument("--top_k", type=int, default=-1, help="Top-k sampling value.")
    parser.add_argument("--history_n", type=int, default=5, help="Number of history steps to consider.")
    parser.add_argument("--callusr_tolerance", type=int, default=3, help="Tolerance for user assistance calls.")
    parser.add_argument("--max_tokens", type=int, default=500, help="Maximum number of tokens to generate.")
    parser.add_argument("--stop_token", type=str, default=None, help="Stop token for generation.")
    parser.add_argument("--enable_thinking", type=bool, default=True, help="Allow the agent to generate 'thinking' steps.")
    parser.add_argument("--som_origin", type=str, default="oss", help="Origin of Screen Object Model data ('oss', 'a11y', etc.).")

    # --- Logging & Execution Settings ---
    parser.add_argument("--test_config_base_dir", type=str, default="evaluation_examples_windows", help="Base directory for test configuration files.")
    parser.add_argument("--domain", type=str, default="all", help="Specify a single domain to test, or 'all'.")
    parser.add_argument("--test_all_meta_path", type=str, default="evaluation_examples_windows/test_all.json", help="Path to the JSON file listing all test tasks.")
    parser.add_argument("--result_dir", type=str, default="./results", help="Directory to save evaluation results.")
    parser.add_argument("--url_set", type=str, default="http://10.140.66.44:8003/v1", help="Comma-separated API URLs for the model endpoint(s).")
    parser.add_argument("--diff_lvl", type=str, default="normal", help="Difficulty level of the benchmark ('normal' or 'hard').")
    parser.add_argument("--trial_id", type=str, default="0", help="A unique identifier for this trial run.")

    # --- Multi-worker Settings ---
    parser.add_argument("--worker_id", type=int, default=0, help="ID of the current worker.")
    parser.add_argument("--num_workers", type=int, default=1, help="Total number of workers.")

    args = parser.parse_args()
    return args

def force_release_path(path: str):
    """
    Finds and kills any process that is using the specified path.
    NOTE: This function is part of the original script but is no longer called in the main
    loop, as a more robust process tree killing mechanism is used in the `finally` block.
    """
    logger.info(f"Checking and force-releasing path: {path}...")
    for proc in psutil.process_iter(['pid', 'name', 'open_files']):
        try:
            if proc.info['open_files']:
                for file in proc.info['open_files']:
                    if file.path.startswith(path):
                        logger.warning(f"Found locking process: PID={proc.info['pid']}, Name={proc.info['name']}, using {file.path}")
                        logger.warning(f"Forcefully terminating PID {proc.info['pid']}...")
                        p = psutil.Process(proc.info['pid'])
                        p.kill()
                        break  # Move to the next process after killing this one.
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass

def restore_snapshot_directory(snapshot_dir: str, active_dir: str):
    """
    Overwrites the active VM directory with the contents of the clean snapshot.

    This function first clears all contents of the active directory and then
    copies everything from the snapshot directory into it, ensuring a fresh
    state for each test run.
    """
    logger.info(f"Clearing active directory: {active_dir}...")
    if os.path.exists(active_dir):
        for filename in os.listdir(active_dir):
            file_path = os.path.join(active_dir, filename)
            try:
                if os.path.isfile(file_path) or os.path.islink(file_path):
                    os.unlink(file_path)
                elif os.path.isdir(file_path):
                    shutil.rmtree(file_path)
            except Exception as e:
                logger.error(f'Failed to delete {file_path}: {e}')
    else:
        os.makedirs(active_dir)
    logger.info("Active directory cleared.")

    logger.info(f"Restoring snapshot from {snapshot_dir} to {active_dir}...")
    # Use dirs_exist_ok=True (Python 3.8+) to copy contents without erroring if the root exists.
    try:
        shutil.copytree(snapshot_dir, active_dir, dirs_exist_ok=True)
    except TypeError:
        # Fallback for older Python versions
        for item in os.listdir(snapshot_dir):
            s_path = os.path.join(snapshot_dir, item)
            d_path = os.path.join(active_dir, item)
            if os.path.isdir(s_path):
                shutil.copytree(s_path, d_path, symlinks=False, ignore=None)
            else:
                shutil.copy2(s_path, d_path)
    logger.info("✅ Snapshot restored successfully.")

def stop_vm(wait_time=30):
    """
    Stops the VM by writing to the QEMU monitor.
    NOTE: This function is part of the original script but is no longer called, as the
    `psutil`-based process killing is more reliable for cleanup.
    """
    qemu_term_path = os.environ.get('QEMU_TERM', '/run/qemu.term')
    logger.info(f"Preparing to shut down VM by sending 'quit' to '{qemu_term_path}'...")
    try:
        with open(qemu_term_path, 'w') as monitor_file:
            monitor_file.write('quit\n')
        logger.info(f"✅ 'quit' command sent. Waiting up to {wait_time} seconds for process to exit...")
        time.sleep(wait_time)
    except FileNotFoundError:
        logger.warning(f"⚠️ QEMU Monitor file '{qemu_term_path}' not found, VM may already be closed.")
    except Exception as e:
        logger.error(f"❌ Error sending quit command: {e}")

def test(args: argparse.Namespace, test_all_meta: dict) -> None:
    """
    Main function to run the evaluation loop over the specified tasks.
    It now manages the VM lifecycle, restarting it for each task.
    """
    scores = []
    max_steps = args.max_steps
    url_set = args.url_set.split(",")
    logger.info("Args: %s", args)

    # --- Collect configuration arguments for logging ---
    cfg_args = {
        "path_to_vm": args.path_to_vm, "headless": args.headless, "action_space": args.action_space,
        "observation_type": args.observation_type, "screen_width": args.screen_width, "screen_height": args.screen_height,
        "sleep_after_execution": args.sleep_after_execution, "max_steps": args.max_steps,
        "max_trajectory_length": args.max_trajectory_length, "agent_name": args.agent_name,
        "model": args.model, "model_type": args.model_type, "infer_mode": args.infer_mode,
        "prompt_style": args.prompt_style, "input_swap": args.input_swap, "language": args.language,
        "history_n": args.history_n, "max_pixels": args.max_pixels, "min_pixels": args.min_pixels,
        "callusr_tolerance": args.callusr_tolerance, "temperature": args.temperature, "top_p": args.top_p,
        "top_k": args.top_k, "max_tokens": args.max_tokens, "stop_token": args.stop_token,
        "enable_thinking": args.enable_thinking, "result_dir": args.result_dir, "worker_id": args.worker_id,
        "num_workers": args.num_workers, "som_origin": args.som_origin
    }

    # --- Initialize Agent ---
    if cfg_args["agent_name"] == "SCALECUA":
        from mm_agents.navi.scalecua_agent import ScaleCUAAgent
        agent = ScaleCUAAgent(screen_width=cfg_args["screen_width"], screen_height=cfg_args["screen_height"], executor_model=cfg_args["model"], enable_thinking=cfg_args["enable_thinking"], api_url=url_set[0])
    else:
        raise ValueError(f"Unknown agent name: {cfg_args['agent_name']}")

    # --- Main Evaluation Loop ---
    for domain in tqdm(test_all_meta, desc="Domain"):
        for example_id in tqdm(test_all_meta[domain], desc="Example", leave=False):
            logger.info(f"\n===== Starting Test: {domain}/{example_id} =====")
            vm_process = None
            task_log_handler = None
            example_result_dir = os.path.join(
                args.result_dir, args.action_space, args.observation_type,
                args.model, args.trial_id, domain, example_id
            )
            os.makedirs(example_result_dir, exist_ok=True)

            try:
                # 1. Preparation: Restore snapshot and start a new VM for each task.
                restore_snapshot_directory(CLEAN_SNAPSHOT_DIR, ACTIVE_VM_DIR)

                logger.info(f"Executing VM start command: {' '.join(START_COMMAND)}...")
                # Use start_new_session=True to create an independent process group.
                # This makes it easier to terminate the VM and all its children reliably.
                vm_process = subprocess.Popen(START_COMMAND, start_new_session=True)

                logger.info(f"Waiting {VM_BOOT_WAIT_TIME} seconds for the VM to boot completely...")
                time.sleep(VM_BOOT_WAIT_TIME)
                logger.info("✅ VM is presumed to be ready.")

                # Initialize the environment for the current task.
                env = DesktopEnv(
                    action_space=agent.action_space,
                    screen_size=(args.screen_width, args.screen_height),
                    headless=args.headless,
                    require_a11y_tree=args.observation_type in ["a11y_tree", "screenshot_a11y_tree", "som"],
                    emulator_ip=args.emulator_ip,
                )

                # 2. Load Task Configuration
                if args.diff_lvl == "normal":
                    config_file = os.path.join(args.test_config_base_dir, f"examples/{domain}/{example_id}.json")
                elif args.diff_lvl == "hard":
                    config_file = os.path.join(args.test_config_base_dir, f"examples_noctxt/{domain}/{example_id}.json")
                else:
                    sys.exit("Invalid value for --diff_lvl. Choose 'normal' or 'hard'.")

                logger.info(f"\nTESTING ON TASK CONFIG PATH: {config_file}")
                with open(config_file, "r", encoding="utf-8") as f:
                    example = json.load(f)

                logger.info(f"[Domain]: {domain}, [Example ID]: {example_id}")
                instruction = example["instruction"]
                logger.info(f"[Instruction]: {instruction}")

                # 3. Setup Per-Example Logging
                logs_dir = os.path.join(example_result_dir, "logs")
                os.makedirs(logs_dir, exist_ok=True)
                task_log_handler = logging.FileHandler(
                    os.path.join(logs_dir, f"task-{args.worker_id}-{datetime_str}.log"),
                    encoding="utf-8"
                )
                task_log_handler.setLevel(logging.DEBUG)
                task_log_handler.setFormatter(formatter)
                root_logger.addHandler(task_log_handler)

                # 4. Run the Task
                lib_run_single.run_single_example(
                    agent, env, example, max_steps, instruction, args, example_result_dir, scores
                )
                env.close()

            except Exception as e:
                logger.error(f"An exception occurred during the test for {domain}/{example_id}: {e}")
                error_traceback = traceback.format_exc()
                logger.error(error_traceback)
                # Log error details to trajectory files.
                with open(os.path.join(example_result_dir, "traj.jsonl"), "a") as f:
                    f.write(json.dumps({
                        "Error": f"Exception in {domain}/{example_id}",
                        "Exception": str(e),
                        "Traceback": error_traceback,
                    }))
                with open(os.path.join(example_result_dir, "traj.html"), "a") as f:
                    f.write(f"<h1>Error: Exception in {domain}/{example_id}</h1>")
                    f.write(f"<p>{e}</p><pre>{error_traceback}</pre>")
            else:
                logger.info(f"Successfully finished {domain}/{example_id}")
            finally:
                # 5. Cleanup Phase: Terminate the VM process tree robustly.
                logger.info("Test finished. Initiating cleanup using psutil...")

                def kill_proc_tree(pid: int, including_parent: bool = True):
                    """Recursively terminates a process and all its children."""
                    try:
                        parent = psutil.Process(pid)
                        children = parent.children(recursive=True)
                        for child in children:
                            logger.info(f"  > Killing child process {child.pid} ({child.name()})")
                            child.kill()
                        if including_parent:
                            logger.info(f"  > Killing parent process {parent.pid} ({parent.name()})")
                            parent.kill()
                    except psutil.NoSuchProcess:
                        logger.warning(f"  > Process {pid} no longer exists. No cleanup needed.")
                    except Exception as e:
                        logger.error(f"  > An error occurred during process tree cleanup: {e}")

                if vm_process:
                    kill_proc_tree(vm_process.pid)

                # Remove the task-specific log handler
                if task_log_handler:
                    root_logger.removeHandler(task_log_handler)
                    task_log_handler.close()

                logger.info("  > Pausing for 3 seconds to ensure resource release...")
                time.sleep(3)
                logger.info("Cleanup complete.")
                logger.info(f"===== Test Ended: {domain}/{example_id} =====\n")

    if not scores:
        logger.info("No examples were completed in this run.")
    else:
        logger.info(f"Final average score: {sum(scores) / len(scores)}")

def get_unfinished(action_space: str, use_model: str, observation_type: str, result_dir: str, trial_id: str, total_file_json: dict) -> dict:
    """
    Filters out tasks that are already completed from a previous run.
    A task is considered complete if a 'result.txt' file exists in its output directory.
    If a task directory exists but is incomplete, its contents are cleared.
    """
    target_dir = os.path.join(result_dir, action_space, observation_type, use_model, trial_id)

    if not os.path.exists(target_dir):
        return total_file_json

    finished = {}
    for domain in os.listdir(target_dir):
        finished[domain] = []
        domain_path = os.path.join(target_dir, domain)
        if os.path.isdir(domain_path):
            for example_id in os.listdir(domain_path):
                if example_id == "onboard":
                    continue
                example_path = os.path.join(domain_path, example_id)
                if os.path.isdir(example_path):
                    if "result.txt" not in os.listdir(example_path):
                        # Clean up the directory of the unfinished task for a fresh start.
                        for file_or_dir in os.listdir(example_path):
                            out_path = os.path.join(example_path, file_or_dir)
                            if os.path.isdir(out_path):
                                shutil.rmtree(out_path)
                            else:
                                os.remove(out_path)
                    else:
                        finished[domain].append(example_id)

    if not finished:
        logger.info("************************** New experiment, no results yet. **************************")
        return total_file_json

    # Remove finished tasks from the total task list.
    for domain, examples in finished.items():
        if domain in total_file_json:
            total_file_json[domain] = [x for x in total_file_json[domain] if x not in examples]

    return total_file_json

def get_result(action_space: str, use_model: str, observation_type: str, result_dir: str, trial_id: str):
    """Calculates and prints the success rate based on existing results."""
    target_dir = os.path.join(result_dir, action_space, observation_type, use_model, trial_id)
    if not os.path.exists(target_dir):
        print("New experiment, no results yet.")
        return

    all_results = []
    for domain in os.listdir(target_dir):
        domain_path = os.path.join(target_dir, domain)
        if os.path.isdir(domain_path):
            for example_id in os.listdir(domain_path):
                example_path = os.path.join(domain_path, example_id)
                if os.path.isdir(example_path) and "result.txt" in os.listdir(example_path):
                    try:
                        with open(os.path.join(example_path, "result.txt"), "r") as f:
                            all_results.append(float(f.read()))
                    except (ValueError, IOError):
                        all_results.append(0.0)

    if not all_results:
        print("New experiment, no results yet.")
    else:
        # Avoid division by zero
        if len(all_results) > 0:
            success_rate = (sum(all_results) / len(all_results)) * 100
            print(f"Current Success Rate: {success_rate:.2f}% ({sum(all_results)}/{len(all_results)})")
        else:
            print("No completed results found to calculate success rate.")

# --- Graceful Shutdown and Server Wait ---
exit_event = Event()

def quit_handler(signo, _frame):
    """Handles graceful shutdown on receiving a signal (e.g., Ctrl+C)."""
    print(f"Interrupted by signal {signo}, shutting down gracefully.")
    exit_event.set()
    sys.exit(0)

def wait_for_server(ip: str, port: int = 5000):
    """
    Waits for a specified server to become available before proceeding.
    NOTE: This function is part of the original script. It is not currently called
    in the main execution flow but is kept for completeness.
    """
    print("Waiting for the server to start...")
    while not exit_event.is_set():
        try:
            response = requests.get(f"http://{ip}:{port}/probe", timeout=7)
            if response.status_code == 200:
                print("Server is up and running:", response.json())
                break
        except requests.exceptions.RequestException as e:
            print(f"Failed to connect to the server: {e}")
            print("Retrying in 5 seconds...")
            exit_event.wait(5)

if __name__ == '__main__':
    # Set this environment variable to prevent tokenizer parallelism issues.
    os.environ["TOKENIZERS_PARALLELISM"] = "false"

    # Set up signal handling for graceful exit.
    for sig in ('TERM', 'HUP', 'INT'):
        signal.signal(getattr(signal, f'SIG{sig}'), quit_handler)

    # Temporarily parse args to get the emulator IP for proxy setup.
    temp_args_for_proxy_setup = config()
    emulator_ip_to_bypass = temp_args_for_proxy_setup.emulator_ip

    # Dynamically update the NO_PROXY environment variable to bypass the local VM.
    # This is crucial in corporate environments or networks with mandatory proxies.
    current_no_proxy = os.environ.get("NO_PROXY", "")
    no_proxy_list = [host.strip() for host in current_no_proxy.split(',') if host.strip()]
    if emulator_ip_to_bypass not in no_proxy_list:
        no_proxy_list.append(emulator_ip_to_bypass)
        new_no_proxy_value = ",".join(no_proxy_list)
        os.environ["NO_PROXY"] = new_no_proxy_value
        print(f"INFO: Updated NO_PROXY environment variable to: {new_no_proxy_value}")

    # --- Main Execution Flow ---
    args = config()
    setup_logging(args)

    with open(args.test_all_meta_path, "r", encoding="utf-8") as f:
        test_all_meta = json.load(f)
    logger.info(f"\nTESTING ON TASK JSON PATH: {args.test_all_meta_path}")

    if args.domain != "all":
        test_all_meta = {args.domain: test_all_meta[args.domain]}

    # For a single worker, filter out already completed tasks.
    if args.num_workers == 1:
        test_file_list = get_unfinished(
            args.action_space, args.model, args.observation_type,
            args.result_dir, args.trial_id, test_all_meta
        )
    else:
        # For multi-worker runs, each worker gets a pre-assigned slice.
        test_file_list = test_all_meta

    left_info = "".join([f"{domain}: {len(test_file_list[domain])}\n" for domain in test_file_list])
    logger.info(f"Tasks to be run:\n{left_info}")

    # --- Distribute tasks among workers ---
    all_tasks_test = [(domain, ex_id) for domain in test_file_list for ex_id in test_file_list[domain]]
    total_tasks = len(all_tasks_test)
    if total_tasks > 0 and args.num_workers > 0:
        tasks_per_worker = total_tasks // args.num_workers
        extra = total_tasks % args.num_workers
        start_index = args.worker_id * tasks_per_worker + min(args.worker_id, extra)
        num_tasks_for_worker = tasks_per_worker + (1 if args.worker_id < extra else 0)
        end_index = start_index + num_tasks_for_worker
        tasks_for_this_worker = all_tasks_test[start_index:end_index]
    else:
        tasks_for_this_worker = []

    # Convert the worker's task list back into a dictionary.
    test_file_list_worker = {}
    for domain, example_id in tasks_for_this_worker:
        test_file_list_worker.setdefault(domain, []).append(example_id)

    # Display current results before starting new tests.
    get_result(
        args.action_space, args.model, args.observation_type,
        args.result_dir, args.trial_id
    )

    # Run the tests.
    test(args, test_file_list_worker)