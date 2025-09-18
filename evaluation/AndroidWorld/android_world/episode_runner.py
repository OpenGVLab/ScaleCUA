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

"""Runs an agent on the environment."""

import json
import dataclasses
from typing import Any, Callable, Optional
from android_world import constants
from android_world.agents import base_agent
from android_world.env import interface
import termcolor
import os


@dataclasses.dataclass()
class EpisodeResult:
  """Represents an episode of an agent interacting with the environment.

  Attributes:
    done: Whether the agent indicated the task is complete.
    step_data: Environment and agent data for each step.
    env_reward: Reward returned by environment, if applicable.
    aux_data: Additional data from the episode which may be used for metrics.
  """

  done: bool
  step_data: dict[str, Any]
  env_reward: Optional[float] = None
  aux_data: Optional[dict[str, Any]] = None


def run_episode(
    goal: str,
    agent: base_agent.EnvironmentInteractingAgent,
    max_n_steps: int = 10,
    start_on_home_screen: bool = False,
    termination_fn: Callable[[interface.AsyncEnv], float] | None = None,
    save_dir: Optional[str] = None,
) -> EpisodeResult:
  """Runs an agent on goal, e.g., "turn off wifi".

  An agent will start from whatever state the provided environment is in and
  run until it determines a task is complete, if the max number of
  steps is reached, of if the termination_fn is True.

  Args:
    goal: The goal instruction for the agent.
    agent: The agent to run on the environment.
    max_n_steps: The max number of steps to allow an agent to run before ending
      an episode.
    start_on_home_screen: Whether to start episode from the home screen or just
      the current screen.
    termination_fn: If provided, a determines whether to terminate an episode.
      For example, for MiniWoB++ tasks, the episode should terminate if there is
      a nonzero reward.

  Returns:
    Data collected during running agent on goal.
  """
  if max_n_steps == 0:
    return EpisodeResult(done=False, step_data={})
  if termination_fn is None:
    termination_fn = lambda env: False

  agent.reset(start_on_home_screen)
  print("reset")
  agent.set_max_steps(max_n_steps)

  output = []
  agent.save_dir = save_dir
  if not os.path.exists(save_dir):
    os.makedirs(save_dir, exist_ok=True)
  logger_data = {
    'save_dir': save_dir,
    'goal': goal,
    'trajectory':[]
  }
  for step_n in range(max_n_steps):
  # for step_n in range(50):
    result = agent.step(goal)
    # import ipdb; ipdb.set_trace()
    response = None
    if result.data.get('action_output', None) != None:
      response = result.data.get('action_output')
    else:
      response = result.data.get('response')
    logger_data['trajectory'].append({'step': step_n, 'response':response, 'step_history': result.data.get('step_history', None)})
    print('Completed step {:d}.'.format(step_n + 1))
    assert constants.STEP_NUMBER not in result.data
    output.append(result.data | {constants.STEP_NUMBER: step_n})
    if termination_fn(agent.env):
      print('Environment ends episode.')
      if save_dir is not None:
        with open(os.path.join(save_dir, 'result.json'), 'w') as f:
          json.dump(logger_data, f, indent=2)
      return EpisodeResult(
          done=True,
          step_data=_transpose_lod_to_dol(output),
      )
    elif result.done:
      print('Agent indicates task is done.')
      if save_dir is not None:
        with open(os.path.join(save_dir, 'result.json'), 'w') as f:
          json.dump(logger_data, f, indent=2)
      return EpisodeResult(
          done=result.done,
          step_data=_transpose_lod_to_dol(output),
      )
  print(
      termcolor.colored(
          'Agent did not indicate task is done. Reached max number of steps.',
          'red',
      )
  )
  if save_dir is not None:
    with open(os.path.join(save_dir, 'result.json'), 'w') as f:
      json.dump(logger_data, f, indent=2)
  return EpisodeResult(
      done=True, step_data=_transpose_lod_to_dol(output)  # pylint: disable=undefined-variable
  )


def _transpose_lod_to_dol(data: list[dict[str, Any]]) -> dict[str, list[Any]]:
  """Transposes a list of dictionaries to a dictionary of lists.

  Args:
    data: A list of dictionaries.

  Returns:
    A dictionary where each key is from the input dictionaries and each value is
    a list of values for that key.
  """
  result = {}
  for d in data:
    for key, value in d.items():
      if key not in result:
        result[key] = []
      result[key].append(value)
  return result


def transpose_dol_to_lod(data: dict[str, list[Any]]) -> list[dict[str, Any]]:
  """Converts a dictionary of lists to a list of dictionaries.

  Useful for post-processing of results; e.g., in colab.

  Args:
    data: A dictionary where each value is a list.

  Returns:
    A list of dictionaries.
  """
  return [dict(zip(data.keys(), values)) for values in zip(*data.values())]
