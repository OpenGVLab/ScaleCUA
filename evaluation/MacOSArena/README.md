# MacOS Arena

**MacOS Arena** is an open-source online evaluation environment for multimodal agents, equipped with a **dockerized macOS environment** and 70 ready-to-use tasks. The pipeline is scalable and easy to use, making it straightforward to evaluate existing agents or integrate new tasks.

## Quick Start
Follow the steps below to quickly set up MacOS Arena and run a test task.

### 1. Download the Repo and Prepare Python Environment

Download the source code and set up a clean Python environment (Python 3.10 is recommended) with all required dependencies installed:
```bash
# Clone the OpenCUA repository
git clone https://github.com/OpenGVLab/OpenCUA.git

# Change directory to the MacOSArena Folder
cd OpenCUA/evaluation/MacOSArena

# Optional: Create a Conda environment for MacOSArena
# conda create -n macos_arena python=3.10
# conda activate macos_arena

# Install required dependencies
pip install -r requirements.txt
```
### 2. Install Docker

**MacOS Arena currently supports Linux systems and Windows Subsystem for Linux (WSL).**

If your platform provides a graphical user interface (GUI), we recommend installing [Docker Desktop for WSL 2](https://docs.docker.com/desktop/install/windows-install/) for Windows users, or [Docker Desktop for Linux](https://docs.docker.com/desktop/install/linux/) if you're using a native Linux system.

For headless environments or minimal setups, you can alternatively install the [Docker Engine](https://docs.docker.com/engine/install/).

### 3. Download System Resources

The MacOS Arena runtime environment depends on two essential system files:  
**`mac_hdd_ng.img`** and **`BaseSystem.img`**.

You can download the files from Hugging Face using the following code snippet. 

*⚠️ Please ensure **50GB** of free disk space before downloading.*

```python
from huggingface_hub import hf_hub_download

# Download BaseSystem image
hf_hub_download(
    repo_id="OpenGVLab/OpenCUA_Env",
    filename="resources/macos/BaseSystem.img",
    local_dir="resources/macos",
    local_dir_use_symlinks=False,
)

# Download mac_hdd_ng image
hf_hub_download(
    repo_id="OpenGVLab/OpenCUA_Env",
    filename="resources/macos/mac_hdd_ng.img",
    local_dir="resources/macos",
    local_dir_use_symlinks=False,
)
```

### 4. Run a Test Script

After setting up the Python environment and downloading system resources, you can run a simple test to verify your setup using [single_run.sh](https://github.com/OpenGVLab/OpenCUA/blob/main/evaluation/MacOSArena/single_run.sh).

First, configure the required environment variables:

```bash
# In single_run.sh, complete the following constants:

# Path to system image files used by the container
export MACOS_ARENA_MAC_HDD_IMG_PATH="/absolute/path/to/mac_hdd_ng.img"
export MACOS_ARENA_BASESYSTEM_IMG_PATH="/absolute/path/to/BaseSystem.img"

# OpenAI API key
export OPENAI_API_KEY="your-api-key-here"

# ================================
# Configurable constants
# ================================

WORK_DIR="path/to/MacOSArena"  # Change to your local path
CONFIG_FILE="config/default_config_linux.yaml"  # For Linux
# CONFIG_FILE="config/default_config.yaml"      # For WSL
...
```

Then, run the test script:
```bash
bash single_run.sh
```
*⏳ If you see an initial SSH connection failure, that is expected — the container may take up to 2 minutes to fully boot. The agent will begin operating once the macOS environment becomes accessible.*

## Run OpenCUA on MacOS Arena
You can use [eval.sh](https://github.com/OpenGVLab/OpenCUA/blob/main/evaluation/MacOSArena/eval.sh) to run a full evaluation on MacOS Arena with a single command.  
Before doing so, make sure to complete the configuration section in the script:

```bash
# ================================
# Required Environment Variables
# ================================

# Path to system image files used by the container
export MACOS_ARENA_MAC_HDD_IMG_PATH="/absolute/path/to/mac_hdd_ng_src.img"
export MACOS_ARENA_BASESYSTEM_IMG_PATH="/absolute/path/to/BaseSystem_src.img"

# Optional: export keys for GPT-based models if used
# export OPENAI_API_KEY="your-api-key-here"
# export ANTHROPIC_API_KEY="your-api-key-here"

# ================================
# Configurable constants
# ================================

WORK_DIR="path/to/MacOSArena"  # Change to your local path

# DOMAINS: Task domain to evaluate.
#          Use "single_app" to test all single-app tasks,
#          or "multi_app" to test all cross-app tasks.
DOMAINS=("multi_app")

# MODELS: List of agent model names to evaluate.
#         Use ("none") for planner + grounder agent (requires PLANNER_EXECUTOR_MODEL).
MODELS=("opencua-3b")


# MODEL_TYPE_LIST: Explicit model types matching MODELS
MODEL_TYPE_LIST=("opencua")

# URL_LIST: Model API URLs for each agent in MODELS (same order).
URL_LIST=("http://localhost:8000")
...
```

To run the evaluation, simply execute:
```bash
bash eval.sh
```
*📌 Make sure that your model API is reachable. OpenCUA is trained based on Qwen2.5-VL, and can be deployed easily using [vLLM](https://github.com/vllm-project/vllm) or [lmdeploy](https://github.com/InternLM/lmdeploy).*

## Acknowledgements
- Built the macOS environment using [sickcodes/Docker-OSX](https://github.com/sickcodes/Docker-OSX)

## Citation
```Bibtex
@article{wang2025mmbenchgui,
  title   = {MMBench-GUI: Hierarchical Multi-Platform Evaluation Framework for GUI Agents},
  author  = {Xuehui Wang, Zhenyu Wu, JingJing Xie, Zichen Ding, Bowen Yang, Zehao Li, Zhaoyang Liu, Qingyun Li, Xuan Dong, Zhe Chen, Weiyun Wang, Xiangyu Zhao, Jixuan Chen, Haodong Duan, Tianbao Xie, Shiqian Su, Chenyu Yang, Yue Yu, Yuan Huang, Yiqian Liu, Xiao Zhang, Xiangyu Yue, Weijie Su, Xizhou Zhu, Wei Shen, Jifeng Dai, Wenhai Wang},
  journal    = {arXiv preprint arXiv:2507.19478},
  year    = {2025}
}
```