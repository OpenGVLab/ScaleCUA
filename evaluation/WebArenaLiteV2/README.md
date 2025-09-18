# 🌐WebArena-Lite-v2 Benchmark Evaluation Guide

WebArena-Lite-v2 is a truthful benchmark that provides a more suitable  framework designed specifically for evaluating pure visual GUI agents in web environments. Developed as an improvement upon [WebArena-Lite](https://github.com/THUDM/VisualAgentBench), it offers 154 tasks across five different types of websites,  encompassing various task modalities including QA, page content matching and more, enabling comprehensive evaluation of GUI agents' capabilities in multiple dimensions. We acknowledge the excellent contributions of  WebArena-related work.

## 📥Preparation (Download and Load Images)

Refer to the [WebArena repository](https://github.com/web-arena-x/webarena/blob/main/environment_docker/README.md) to download the required images. Note that at this stage, you only need to **download** six docker images for five websites (Shopping, ShoppingAdmin, Reddit,  Gitlab, OpenStreetMap). You don't need to download the Wikipedia image  or create containers. The download list is as follows:

- 🛒Shopping website: `shopping_final_0712.tar`
- ⚙️ShoppingAdmin website: `shopping_admin_final_0719.tar`
- 💬Reddit website: `postmill-populated-exposed-withimg.tar`
- 🦊Gitlab website: `gitlab-populated-final-port8023.tar`
- 🗺️OpenStreetMap website: `openstreetmap-website-db.tar.gz`, `openstreetmap-website-web.tar.gz`

Place all these image files in a single directory, modify `ARCHIVES_LOCATION` in `launcher/01_docker_load_images.sh` to point to this directory, then execute the following command to load the images:

```bash
bash launcher/01_docker_load_images.sh
```

## 🛠️Configure the Running Environment

1. Install the necessary packages. Run `pip install -r requirements.txt` to install all python dependencies.
2. Refer to the Web section in [ScaleCUA Playground documentation](https://github.com/OpenGVLab/ScaleCUA/blob/main/playground/README.md) to configure a workable Web environment.

## 🚀Starting the Evaluation

1. **Website Environment Initialization**: Before each evaluation, you **must reinitialize the environment**
   
   - Configure Docker container startup parameters in ` launcher/00_vars.sh`. Important configuration properties include:
     - `PUBLIC_HOSTNAME`：Current host IP address, this IP address must be accessible from the evaluation server.
     - `{WEBSITE}_PORT`: Port numbers for each evaluation website. Recommended to use the default range of 6666~6671.
     - `HTTP_PROXY/HTTPS_PROXY/NO_PROXY`: Proxy settings  especially for the OpenStreetMap website. If your server cannot normally connect to the internet, setting this proxy is necessary to access  OpenStreetMap's nominatim server. The other four websites can  run normally without internet access.
   - Execute `python launcher/start.py` to initialize Docker and instantiate tasks.
   
2. **Configuration Files**: Two files need to be configured
   - `config/agent/scalecua_agent.yaml`: Parameter meanings are explained in file comments. We recommend using `lmdeploy` or `vllm` to deploy models. Generally, you only need to modify `base_url` and `model` (the model name on the API side).
   - `config/env/web.yaml`: Parameter meanings are explained in file comments, with details available in [ScaleCUA Playground documentation](https://github.com/OpenGVLab/ScaleCUA/blob/main/playground/README.md). You need to modify the `explicitly_allowed_ports` list to match the port numbers set in the first step. Other parameters generally don't need modification.

3. **Running the Evaluation**: One-click startup scripts are provided. 

   To run within Docker, use:

   ```bash
   bash start_scalecua_agent_evaluation_with_docker.sh
   ```

   Without Docker, use:

   ```bash
   bash start_scalecua_agent_evaluation_wo_docker.sh
   ```

   Startup script parameters include:

   - `--platform`: Options are web (Pure Web) / ubuntu_web (Ubuntu Web). For differences, refer to [ScaleCUA Playground documentation](https://github.com/OpenGVLab/ScaleCUA/blob/main/playground/README.md). The stability of Ubuntu Web is currently uncertain, so the default is web.
   - `--env_config_path`: Environment configuration file, default is `config/env/web.yaml`.
   - `--agent_config_path`: Agent model configuration file, default is `config/agent/scalecua_native_agent.yaml` for "native agent" mode, or you can use `config/agent/scalecua_agentic_workflow.yaml` for "agentic workflow" mode.
   - `--task_config_path`: Task root directory, default is `tasks`.
   - `--num_workers`: Number of parallel evaluation processes. default is 1. Currently, only web platform supports multi-process parallelism, ubuntu web platform doesn't support it so far. ★**Note that tasks exhibit minimal non-orthogonality, where execution order may impact evaluation metrics. We recommend sequential execution to prevent interaction interference. Maintaining continuous website instances rather than restarting for each task is motivated by considerations of time efficiency and complexity reduction, avoiding the overhead of Docker restarts and dynamic port mapping complications.**
   - `--exp_name`: Experiment name, used to organize result folders.
   - `--max_steps`: Maximum number of steps for model execution, default is 15.

4. **Evaluation Results**: The evaluation results will be saved in the `results/{exp_name}` folder, containing individual task folders `results/{exp_name}/{task_id}`. The `results/{exp_name}/{task_id}/trajectory` folder includes screenshots of each step, while `results/{exp_name}/{task_id}/result.json` contains the task completion status. The overall evaluation results are located at `results/{exp_name}/results.jsonl`.

## ✨Feature

This framework is highly flexible, being an extension of our [playground](https://github.com/OpenGVLab/ScaleCUA/blob/main/playground/), and supports:

- Customizing additional tasks: You can refer to the `tasks` folder and `config/env/webarena/tasks` folder to set up additional tasks. You can even integrate different Benchmarks entirely into this framework.
- Customizing Native Agents and Agentic Workflows: You can customize model workflows in the `agents` folder, just ensure that each step returns actions in the correct format.
- Customizing prompts: You can freely modify the prompts used for planning and grounding in the `config/prompt_template` folder. For ScaleCUA models, it's best to use our provided default prompts.

## 🙏Acknowledgement

Thanks to [WebArena](https://github.com/web-arena-x/webarena), [VisualAgentBench(WebArena-Lite)](https://github.com/THUDM/VisualAgentBench),  [AgentS](https://github.com/simular-ai/Agent-S) etc. made brilliant contribution to the GUI Agent development.
