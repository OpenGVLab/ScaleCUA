# AndroidWorld

## Installation
Please refer to [AndroidWorld README](docs/README_AndroidWorld.md)

## OpenCUA Model Evaluation

1. **Launch the Android emulator first (example):**
   ```bash
   emulator -avd AndroidWorldAVD -no-snapshot -grpc 8554
    ```

2. **After deploying your model API with `vLLM` (refer to [model development](../README.md#-model-development)), configure the required parameters in the `_get_agent()` function inside `run.py`, including `model_name` (the name of your model), `model_address` (the API endpoint), and `mode` (the evaluation mode, which can be either `'grounder'` for grounding evaluation or `'agent'` for native agent evaluation).**
   
3. **Run the evaluation using the following script:**

    ```bash
    ./eval.sh [AGENT_NAME] [CONSOLE_PORT] [CHECKPOINT_DIR] [GRPC_PORT]
    ````

    Where:

    * **\[AGENT\_NAME]** is the name of the agent you want to evaluate
    * **\[CONSOLE\_PORT]** is the port for the agent’s console
    * **\[CHECKPOINT\_DIR]** is the path to the directory containing your model checkpoints
    * **\[GRPC\_PORT]** is the port for the gRPC service

## Qwen3-VL Model Evaluation

We have adapted the prompts and action space of the Qwen3-VL series models to reproduce their evaluation results.

1. **Launch the Android emulator first (example):**
   ```bash
   emulator -avd AndroidWorldAVD -no-snapshot -grpc 8554
   ```

2. **After deploying your model API with `vLLM` (refer to [model development](../README.md#-model-development)), configure the `model_url` and `model_name`, e.g., `http://<ip>:8000/v1` and `Qwen3-VL-8B-Instruct`.**

3. **Run the evaluation using the following script (example):**
    ```
    python run.py --agent_name qwen3vl --console_port 5554 --grpc_port 8554 --perform_emulator_setup=true --qwen3vl_model_base_url model_url --qwen3vl_model_name model_name --qwen3vl_model_api_key EMPTY --checkpoint_dir runs/qwen3vl_8b_instruct
    ```