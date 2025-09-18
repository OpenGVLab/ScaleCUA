# ScaleCUA Playground

## QuickStart

- Deploy the [ScaleCUA](https://poe.com/chat/392p2eka2x20m1cg0e8) models with [vLLM](https://github.com/vllm-project/vllm) following our [guidance](../evaluation/README.md#-model-development), and then record the model name and URL
- Update `base_url` and `model` as instructed in our model configuration guidance.
- Configure the appropriate environment parameters as instructed in our environment configuration guidance

Then, run it using the following command:
```bash
python agent_run_interactive.py \
  --platform ubuntu \ # ubuntu / web / android / ubuntu_web
  --env_config_path playground/config/envs/ubuntu.yaml \
  --agent_config_path playground/config/agent/scalecua_native_agent.yaml
```

## Model Configuration

### Native Agentic Model

The `scalecua_native_agent.yaml` configures a native agent with one model responsible for UI grounding and planning:

- **engine_type**: Specifies API compatibility (openai format).
- **model**: Name of the specific model being used.
- **base_url**: Network address where the AI model is deployed.
- **grounding_width/height**: Resolution grid size for location understanding.
- **prompt_template**: File containing templates for prompts.
- **enable_thinking**: When true, enables the model's reasoning step for improved responses.
- **resize_corrds**: Whether to use `smart_resize` for coordinate rescaling (common for qwen25vl model).

### Agentic Workflow

The `scalecua_agentic_workflow.yaml` configures two different AI models for UI planning and grounding, respectively:

- **planner_model**: AI model used for planning tasks.
- **ui_grounding_model**: AI model used for predict coordinate.

Each model has its own specific configuration parameters similar to those described in the native agent setup.

## Environment Configuration

### Ubuntu

We use Docker to provide the Ubuntu OS playground. Ensure the Docker  service is running on your host machine, then configure the following:

- **vm_path**: Absolute file path to the virtual machine's disk image (.qcow2 format). You can download our [playground file](https://poe.com/chat/392p2eka2x20m1cg0e8), which comes with pre-installed applications and includes files.
- **connect_max_try**: Maximum number of connection attempts before failing (default: 3).

### Web

We provide two web environments based on Playwright: a pure web  environment ("Pure Web") and a web environment running on Ubuntu  ("Ubuntu Web"). Both environments share the same configuration file. You can find the config for web in `playground/config/envs/web.yaml`.

- **server_path**: Server path in format `http://{ip}:{port}`. Only required for Ubuntu Web.
- **width**: Browser rendering width in pixels (default: 1280px)
- **height**: Browser rendering height in pixels (default: 720px)
- **dpr**: Device Pixel Ratio - 1.5 for Windows, 1.0 for Linux (default: 1.0)
- **wait_timeout**: Page load timeout in seconds (default: 60s)
- **web_proxy**: Playwright network proxy in format `http://{name}:{key}@{ip}:{port}` (optional)
- **explicitly_allowed_ports**: Additional ports to expose beyond HTTP/HTTPS (optional)

#### Pure Web Setup

Setting up the Pure Web environment is straightforward by installing chromium for Playwright:
```bash
playwright install chromium
```

#### Ubuntu Web Setup

The Ubuntu Web environment runs in a Docker container (~2.3GB)，you can build docker image by yourself or download the pre-configured image `ubuntu-webarena-lite-v2-test` from [link](https://huggingface.co/OpenGVLab/OpenCUA_Env/tree/main/resources/web). Next we provide these two configuration methods.

First navigate to the setup directory:

```bash
cd envs/web/ubuntu_web_setup
```

**Build image by yourself** (about 5~10min)

```bash
docker build -t ubuntu-webarena-lite-v2-test:1.0 .
docker images # check whether the image is ready
```

**Download and load the pre-configured image**

```bash
# First download ubuntu-webarena-lite-v2-test.tar from huggingface
docker load -i {your_path}\ubuntu-webarena-lite-v2-test.tar
docker images # check whether the image is ready
```

After load the image successfully, configure `SERVICE_PORT` and `VNC_PORT` in the `.env` file. Port mapped to the host machine. Then, Start the container:

```bash
docker-compose up -d
```

This will launch an Ubuntu environment with a web browser that can be controlled via our API and optionally monitored through VNC (suggest using [RealVNCViewer](https://www.realvnc.com/en/connect/download/vnc/)).

### Android

You can find the config for android in `playground/config/envs/android.yaml`.Configure the following settings to connect to an Android device or emulator:
- **server_path**: Host address where the Android API server is running (e.g., http://127.0.0.1). Refer to [API Setup Tutorial](envs/android/env_api/README.md)

- **platform**: Specifies the target platform (set to android)

- **manager_port**: Port where the API listens (e.g., 8002)

- **avd_name**: Android Virtual Device name or device ID.  In Docker mode, this is the emulator name; on a local machine or real device, use `adb devices` to show  the ID of adb devices:

- **docker**: Determine the execution environment for the Android emulator. When set to `true`, the emulator will be launched within a Docker container. If set to `false`, the system will instead use an emulator running on the host machine or a connected physical device; this option requires that the device is in developer mode and accessible via ADB.

- **docker_args**: Contain settings that are only used when the docker parameter is set to true. It allows you to specify configuration details for the Docker environment, including the image_name, which defines the Docker image to be used (e.g., android_eval:latest), and the port, which sets the internal port for communication within the container, defaulting to 6060.



# Acknowledge
We draws significant inspiration from the pioneering efforts of [AgentS](https://github.com/simular-ai/Agent-S), [WebArena](https://github.com/web-arena-x/webarena), [OSWorld](https://github.com/xlang-ai/OSWorld) and [AndroidLab](https://github.com/THUDM/Android-Lab). We are grateful for their foundational contributions to the field of GUI Agent development.

