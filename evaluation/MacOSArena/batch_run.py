import argparse
import datetime
import json
import time
from pathlib import Path

from controllers.env import MacOSEnv
from utils.logger import ProjectLogger
from mm_agents.agent import PromptAgent
from mm_agents.aguvis_agent import AguvisAgent
from mm_agents.uitars_agent import UITARSAgent
from mm_agents.internvl_agent import InternvlAgent
from mm_agents.simple_qwenvl_agent import SimpleQwenvlAgent

script_dir = Path(__file__).resolve().parent
logger = ProjectLogger(log_dir=script_dir / "logs")

MODEL_TYPE_LIST = {
    "gpt": lambda model, url: PromptAgent(model=model),  
    "claude": lambda model, url: PromptAgent(model=model),
    "uitars": lambda model, url: UITARSAgent(model=model, url=url),
    "aguvis": lambda model, url: AguvisAgent(planner_model=None, executor_model=model, url=url),
    "opencua": lambda model, url: InternvlAgent(model=model, url=url),
    "qwen25vl": lambda model, url: InternvlAgent(model=model, url=url),
    "qwen25vl-no-local-history": lambda model, url: SimpleQwenvlAgent(model=model, url=url),
}

def get_all_tasks(domains):
    task_root = Path("tasks")
    if "all" in domains or "single_app" in domains:
        domains = ["calendar", "clock", "finder", "mac_system_settings", "notes", "reminders", "safari", "terminal", "vscode"]

    task_paths = []
    for domain in domains:
        domain_path = task_root / domain
        if domain_path.exists():
            task_paths.extend(sorted(domain_path.glob("*.json")))
    return task_paths

def wait_for_ssh(env: MacOSEnv, max_wait: int = 300, interval: int = 5):
    total_waited = 0
    attempt = 1
    while total_waited < max_wait:
        try:
            logger.info(f"[SSH Attempt {attempt}] Trying to connect...")
            env.connect_ssh()
            transport = env.ssh_client.get_transport() if env.ssh_client else None
            if not transport or not transport.is_active():
                raise ConnectionError("SSH transport not active after connect()")
            logger.info("✅ SSH connected successfully.")
            time.sleep(15)
            return
        except Exception as e:
            logger.warning(f"[SSH Attempt {attempt}] Failed: {type(e).__name__}: {e}")
            time.sleep(interval)
            total_waited += interval
            attempt += 1
    raise TimeoutError(f"❌ SSH connection failed after waiting {max_wait} seconds.")


def do_single_task(env: MacOSEnv, agent, task_path: Path, result_path: Path, max_steps: int = 50):
    task_name = task_path.stem
    domain_path = result_path / task_path.parent.name / task_name
    domain_path.mkdir(parents=True, exist_ok=True)

    env._reset_env()
    wait_for_ssh(env)
    env.init_task(task_path)
    
    agent.reset()

    obs = env._get_obs()
    done = False
    step_idx = 0
    response_log_path = domain_path / "response.txt"
    traj_path = domain_path / "traj.jsonl"
    env.start_recording()

    with open(response_log_path, "w", encoding="utf-8") as resp_file, open(traj_path, "w") as traj_file:
        while not done and step_idx < max_steps:
            response, actions = agent.predict(env.task.instruction, obs)
            resp_file.write(f"Step {step_idx + 1}:\n{response}\n\n")

            step_actions, step_rewards, step_infos = [], [], []

            for action in actions:
                obs, reward, done, info = env.step(action)
                step_actions.append(action)
                step_rewards.append(reward)
                step_infos.append(info)
                if done:
                    break

            action_timestamp = datetime.datetime.now().strftime("%Y%m%d@%H%M%S")
            screenshot_file = domain_path / f"step_{step_idx + 1}_{action_timestamp}.png"
            with open(screenshot_file, "wb") as f:
                f.write(obs['screenshot'])

            traj_file.write(json.dumps({
                "step_num": step_idx + 1,
                "action_timestamp": action_timestamp,
                "actions": step_actions,
                "rewards": step_rewards,
                "done": done,
                "infos": step_infos,
                "screenshot_file": screenshot_file.name
            }) + "\n")

            step_idx += 1

    result = env.evaluate_task()
    result_path_file = domain_path / "result.txt"
    with open(result_path_file, "w", encoding="utf-8") as f:
        json.dump({
            "completed": bool(result),
            "steps_used": step_idx,
            "max_steps": max_steps
        }, f, indent=2)

    env.end_recording(str(domain_path / "recording.mp4"))


def main(
    domains,
    models,
    model_type_list,
    url_list,
    planner_executor_model,
    exec_model_url_list,
    model_sub_dir,
    repeat_task,
    config_file,
    _result_root
):
    task_paths = get_all_tasks(domains)
    if models == ["none"]:
        models = []
        
    model_type_list = model_type_list or [None] * len(models)
    assert len(model_type_list) == len(models), "model_type_list must match models in length."
    
    url_list = url_list or [None] * len(models)
    assert len(url_list) == len(models), "url_list must match models in length."

    for model, model_type, url in zip(models, model_type_list, url_list):
        print(f"=== Running model: {model} ===")
        if model_type is None:
            if "claude" in model.lower() or "gpt" in model.lower():
                AgentClass = PromptAgent
                get_model_name = lambda a: a.model
            elif "ui_tars" in model.lower() or "uitars" in model.lower():
                AgentClass = UITARSAgent
                get_model_name = lambda a: a.model
            elif "aguvis" in model.lower():
                AgentClass = lambda: AguvisAgent(planner_model=None, executor_model=model)
                get_model_name = lambda a: a.executor_model
            elif "gui_v" in model.lower() or "opencua" in model.lower():
                AgentClass = InternvlAgent
                get_model_name = lambda a: a.model
            elif "simple" in model.lower():
                AgentClass = SimpleQwenvlAgent
                get_model_name = lambda a: a.model
            else:
                raise ValueError(f"Unknown model type for: {model}")

            agent_for_name = AgentClass(url=url) if "aguvis" in model.lower() else AgentClass(model=model, url=url)
            model_name = get_model_name(agent_for_name)
        else:
            model_key = model_type
            
            matched_key = None
            for key in MODEL_TYPE_LIST:
                if key in model_key:
                    matched_key = key
                    break
                    
            if matched_key is None:
                raise ValueError(f"Unknown or unsupported model/model_type: {model_key}")
            
            AgentClass = MODEL_TYPE_LIST[matched_key]
            if matched_key == "aguvis":
                agent_for_name = AgentClass(model, url=url)
                get_model_name = lambda a: a.executor_model
            else:
                agent_for_name = AgentClass(model, url=url)
                get_model_name = lambda a: a.model

            model_name = get_model_name(agent_for_name)

        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        subfolder = model_sub_dir if model_sub_dir else timestamp
        result_root = Path(_result_root) / model_name / subfolder
        result_root.mkdir(parents=True, exist_ok=True)

        with open(result_root / "meta.txt", "w", encoding="utf-8") as meta_file:
            meta_file.write(f"model: {model_name}\n")
            meta_file.write(f"domains: {','.join(domains)}\n")

        for task_path in task_paths:
            task_name = Path(task_path).relative_to("tasks").with_suffix("")  # e.g., safari/3
            result_file = result_root / task_name / "result.txt"
            if not repeat_task and result_file.exists():
                logger.info(f"[SKIP] {task_name} already has result.txt")
                continue
            if model_type is None:
                agent = AgentClass(url=url) if "aguvis" in model.lower() else AgentClass(model=model, url=url)
            else:
                agent = MODEL_TYPE_LIST[matched_key](model, url)
            macos_env = MacOSEnv(config_file=config_file)
            do_single_task(macos_env, agent, task_path, result_root)
            macos_env.close_connection()

    valid_pairs = []
    for pair in planner_executor_model:
        if isinstance(pair, (list, tuple)) and len(pair) == 2:
            valid_pairs.append(tuple(pair))
        else:
            logger.warning(f"[SKIP] Invalid planner-executor pair: {pair}")

    planner_executor_model = valid_pairs
    if len(planner_executor_model):
        for idx, (planner_model, executor_model) in enumerate(planner_executor_model):
            exec_url = exec_model_url_list[idx] if exec_model_url_list else None
            
            print(f"=== Running planner-executor pair: {planner_model} + {executor_model} ===")
            model_name = f"{planner_model}-{executor_model}"
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            subfolder = model_sub_dir if model_sub_dir else timestamp
            result_root = Path(_result_root) / model_name / subfolder
            result_root.mkdir(parents=True, exist_ok=True)

            with open(result_root / "meta.txt", "w", encoding="utf-8") as meta_file:
                meta_file.write(f"planner: {planner_model}\n")
                meta_file.write(f"executor: {executor_model}\n")
                meta_file.write(f"domains: {','.join(domains)}\n")

            for task_path in task_paths:
                task_name = Path(task_path).relative_to("tasks").with_suffix("")
                result_file = result_root / task_name / "result.txt"
                if not repeat_task and result_file.exists():
                    logger.info(f"[SKIP] {task_name} already has result.txt")
                    continue

                agent = AguvisAgent(planner_model=planner_model, executor_model=executor_model, url=exec_url)
                macos_env = MacOSEnv(config_file=config_file)
                do_single_task(macos_env, agent, task_path, result_root)
                macos_env.close_connection()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Batch run GUI agent tasks on macOS.")
    parser.add_argument("--domains", nargs="+", default=["all"], help="List of task domains to run (default: all)")
    parser.add_argument("--models", nargs="*", default=["ui_tars_15_7b"], help="List of agent models to run")
    parser.add_argument("--url_list", nargs="*", default=None, help="List of native agent model API URLs for each model (for gpt and claude, use None)")
    parser.add_argument("--model_type_list", nargs="*", default=None,
                        help="Explicit model type list to use for agent models (e.g., gpt, aguvis, uitars, etc.), must match models in order")
    parser.add_argument("--planner_executor_model", nargs="*", action="append", default=[], metavar=("PLANNER", "EXECUTOR"),
                        help="Planner-executor model pairs, e.g., --planner_executor_model gpt-4o uitars")
    parser.add_argument("--exec_model_url_list", nargs="*", default=None, help="List of executor model API URLs for each planner-grounder model")
    parser.add_argument("--model_sub_dir", type=str, default=None, help="Optional subdirectory name for results")
    parser.add_argument("--repeat_task", action="store_true", help="Repeat every task even if result.txt exists")
    parser.add_argument("--config_file", type=str, default="config/default_config.yaml", help="Path to YAML config file for MacOSEnv")
    parser.add_argument("--result_root", type=str, default="/nvme/wuzhenyu/results", help="Path to save results")
    

    args = parser.parse_args()

    main(
        domains=args.domains,
        models=args.models,
        model_type_list = args.model_type_list,
        url_list=args.url_list,
        planner_executor_model=args.planner_executor_model,
        exec_model_url_list = args.exec_model_url_list,
        model_sub_dir=args.model_sub_dir,
        repeat_task=args.repeat_task,
        config_file=args.config_file,
        _result_root=args.result_root
    )
