from controllers.env import MacOSEnv
from pathlib import Path
from utils.logger import ProjectLogger

import time
from mm_agents.agent import PromptAgent
from mm_agents.aguvis_agent import AguvisAgent
from mm_agents.uitars_agent import UITARSAgent
from mm_agents.simple_qwenvl_agent import SimpleQwenvlAgent
import datetime
import os
import json
import argparse

script_dir = Path(__file__).resolve()

# Logger setup
logger = ProjectLogger(log_dir=script_dir / "logs")

def wait_for_ssh(env: MacOSEnv, max_wait: int = 300, interval: int = 5):
    total_waited = 0
    attempt = 1
    while total_waited < max_wait:
        try:
            logger.info(f"[SSH Attempt {attempt}] Trying to connect...")
            env.connect_ssh()
            # Check actual transport status
            transport = env.ssh_client.get_transport() if env.ssh_client else None
            if not transport or not transport.is_active():
                raise ConnectionError("SSH transport not active after connect()")
            logger.info("✅ SSH connected successfully.")
            # wait for boot
            time.sleep(15)
            return
        except Exception as e:
            logger.warning(f"[SSH Attempt {attempt}] Failed: {type(e).__name__}: {e}")
            time.sleep(interval)
            total_waited += interval
            attempt += 1
    raise TimeoutError(f"❌ SSH connection failed after waiting {max_wait} seconds.")


def do_single_task(env: MacOSEnv, agent: PromptAgent, max_steps: int = 50):
    obs = env._get_obs() # Get the initial observation
    done = False
    step_idx = 0
    example_result_dir = "results/example_run"
    scores = []
    env.start_recording()
    while not done and step_idx < max_steps:
        response, actions = agent.predict(
            env.task.instruction,
            obs
        )
        # logger.info("Response: "  + response)
        for action in actions:
            # Capture the timestamp before executing the action
            action_timestamp = datetime.datetime.now().strftime("%Y%m%d@%H%M%S")
            logger.logger.info("Step %d: %s", step_idx + 1, action)
            obs, reward, done, info = env.step(action)

            logger.logger.info("Reward: %.2f", reward)
            logger.logger.info("Done: %s", done)
            # Save screenshot and trajectory information
            with open(os.path.join(example_result_dir, f"step_{step_idx + 1}_{action_timestamp}.png"),
                      "wb") as _f:
                _f.write(obs['screenshot'])
            with open(os.path.join(example_result_dir, "traj.jsonl"), "a") as f:
                f.write(json.dumps({
                    "step_num": step_idx + 1,
                    "action_timestamp": action_timestamp,
                    "action": action,
                    "reward": reward,
                    "done": done,
                    "info": info,
                    "screenshot_file": f"step_{step_idx + 1}_{action_timestamp}.png"
                }))
                f.write("\n")
            if done:
                logger.logger.info("The episode is done.")
                break
        step_idx += 1
    result = env.evaluate_task()
    logger.logger.info("Result: %.2f", result)
    scores.append(result)
    with open(os.path.join(example_result_dir, "result.txt"), "w", encoding="utf-8") as f:
        f.write(f"{result}\n")
    env.end_recording(os.path.join(example_result_dir, "recording.mp4"))

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config_file", type=str, default="config/default_config_linux.yaml", help="Path to env config YAML file")
    args = parser.parse_args()
    # ======
    # For dedug only
    # ======
    
    # Initialize the environment with default config
    macos_env = MacOSEnv(config_file=args.config_file)
    
    # Select agent 
    agent = PromptAgent()
    # agent = AguvisAgent(executor_model="uground7b")
    # agent = SimpleQwenvlAgent()
    # agent = AguvisAgent(executor_model="Aguvis-72B-720P")
    # agent = UITARSAgent(model="ui_tars_15_7b")
    agent.reset()
    
    # Restart the docker if needed
    macos_env._reset_env()
    wait_for_ssh(macos_env)
    
    # Connect to Docker container
    macos_env.connect_ssh()
    task_path = Path("tasks/tasks/clock_1.json").resolve()
    macos_env.init_task(task_path)
    
    do_single_task(macos_env,  agent)
    # Close the SSH connection
    macos_env.close_connection()

if __name__ == '__main__':
    main()