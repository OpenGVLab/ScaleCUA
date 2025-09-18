# OpenCUA 

## AndroidLab Environment Setup
Please refer to [AndroidLab README](docs/README_AndroidLab.md)

Note:We made slight modifications to the Dockerfile to simplify the setup of the Docker image environment. Please refer to [Dockerfile](Dockerfile)

## OpenCUA Model Evaluation

OpenCUA does **not** use AndroidLab’s original SoM/XML interfaces. Instead, it feeds raw **screen screenshots directly to the model**, which predicts the next action.

### 1. Serve your model via `vLLM`
Expose OpenCUA Agent as an HTTP API, referring to [model development](../README.md#-model-development)

Record the `base_url` (e.g., `http://127.0.0.1:23333/v1`) and any `api_key` if required.

### 2. Edit `config.yaml`

Fill in the API fields and set the task type to **`PixellevelMobileTask_AutoTest`**. Other parameters (concurrency, storage dirs, evaluation ranges, etc.) can follow AndroidLab’s `config.yaml` and your VM resources.

```yaml
agent:
    name: OpenAIAgent
    args:
        api_key: "YOUR API KEY"
        api_base: "YOUR API BASE"
        model_name: "YOUR MODEL NAME"
        max_new_tokens: 512

task:
    class: PixellevelMobileTask_AutoTest
    args:
        save_dir: "./logs/evaluation"
        max_rounds: 25
        request_interval: 3

eval:
  avd_name: Pixel_7_Pro_API_33
  avd_log_dir: ./logs/evaluation
  docker: True
  docker_args:
    image_name: android_eval:latest
    port: 6060
```

### 3. Configure `eval.sh`

Set paths here—**`BASE_LOG_DIR` must match `eval.avd_log_dir` in `config.yaml`**. Also:

- Point `CONFIG` to your `config.yaml` (contains API info, `PixellevelMobileTask_AutoTest`, etc.).
- (Optional) Provide judge args for `generate_result.py`:  
  `--judge_model`, `--api_base`, `--api_key` (defaults shown below).
- (Optional) Pass a subset of tasks: `TASK_IDS="taskid_1,taskid_3"`.
### 4. Run the evaluation

```bash
bash eval.sh <NAME> <PARALLEL> <CONFIG> [TASK_IDS] [JUDGE_MODEL] [API_BASE] [API_KEY]
# e.g.
bash eval.sh OpenCUA_7B 3 config.yaml taskid_1,taskid_5 gpt-4o-2024-05-13 https://api.openai.com/v1 $OPENAI_API_KEY
```