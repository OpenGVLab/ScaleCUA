# ScaleCUA: Scaling Open-Source Computer Use Agents with Cross-Platform Data

<p align="center">
&nbsp&nbsp📑 <a href="https://arxiv.org/abs/2509.xxx">Paper</a>&nbsp&nbsp | &nbsp&nbsp🤗 <a href="https://huggingface.co/datasets/OpenGVLab/ScaleCUA-Data">Dataset</a>&nbsp&nbsp | &nbsp&nbsp🤖 <a href="https://huggingface.co/collections/OpenGVLab/scalecua-68c912cf56f7ff4c8e034003">Model</a>&nbsp&nbsp | &nbsp&nbsp🖥️  <a href="https://github.com/OpenGVLab/OpenCUA">Model Demo</a>&nbsp&nbsp 
</p>

<div style="max-width:900px;margin:0 auto;">

Vision-Language Models (VLMs) have enabled computer use agents (**CUAs**) that operate GUIs autonomously with great potential. 
However, developing robust CUAs requires extensive in-domain knowledge about software interfaces and operations. 
Unlike image–text pairs that are widely available on the Internet, computer-use data, particularly operation trajectories, are rare, costly to collect. 
Consequently, progress in this field remains constrained by both data scale and the limited transferability of existing VLMs. 
In this work, we introduce **ScaleCUA**, a step toward scaling open-source CUAs. It offers a large-scale dataset spanning 6 operating systems and 3 task domains, via a closed-loop pipeline uniting automated agents with human experts. Trained on this scaled-up data, ScaleCUA can operate seamlessly across platforms. 
Specifically, it delivers strong gains over baselines (+**26.6** on WebArena-Lite-v2, +**10.7** on ScreenSpot-Pro) and sets new state-of-the-art results (**94.4**\% on MMBench-GUI L1-Hard, **60.6**\% on OSWorld-G, **47.4**\% on WebArena-Lite-v2). These findings underscore the power of data-driven scaling for general-purpose cross-platform CUAs. 

<img width="3762" height="2558" alt="scalecua_teaser" src="https://github.com/user-attachments/assets/1c05d713-33d2-4705-9941-053572ccf699" />


## 🤖 Video Demo
**<a id="draggan_demo"></a>**

https://github.com/user-attachments/assets/15da764b-d586-490c-b852-cd1d0b42bb2d

## 📋 Table of Contents
- [ScaleCUA: An Open-Source Agent for Cross-Platform GUI Automation](#scalecua-an-open-source-agent-for-cross-platform-gui-automation)
  - [📋 Table of Contents](#-table-of-contents)
  - [🎉 News](#-news)
  - [🚀 Key Features](#-key-features)
  - [📂 Project Structure](#-project-structure)
  - [⚙️ Setup](#️-setup)
  - [🎮 Playground](#-playground)
  - [📊 Evaluation](#-evaluation)
  - [💻 Training](#-training)
  - [💐 Acknowledgements](#-acknowledgements)
  - [⚖️ License](#️-license)
  - [📜 Citation](#-citation)

## 🎉 News
- `2025/09/19`: ScaleCUA-Data is being uploaded to HuggingFace. Please be patient.
- `2025/09/19`: We have released models and code of ScaleCUA.

## 🚀 Key Features

  * **ScaleCUA-Data:** A large-Scale cross-platform dataset spanning 6 operating systems and 3 GUI-centric task domains.
  * **ScaleCUA-Models:** An cross-platform general-purpose agent that excels at GUI-centric task completion on various environments.
  * **SFT Codebase:** A comprehensive training framework that supports training computer use agent based on Qwen2.5-VL and InternVL.
  * **Interactive Playground:** A series of realistic, interactive environments across Ubuntu, Android, and Web.
  * **Online Evaluation Suite:** A set of online benchmarks to evaluate agents' capabilities of task completion on various platforms.

<img width="2828" height="1825" alt="infer_mode" src="https://github.com/user-attachments/assets/cccde5ba-641e-4e9f-8fdd-7628c0b5f4f3" />


## 📂 Project Structure

This repository is organized into three main components:

  * **[`evaluation`](./evaluation)**: Contains all the code and benchmarks for the end-to-end evaluation of our agents.
  * **[`playground`](./playground)**: Provides interactive environments (Android, Ubuntu, Web) and model implementations for users to experience the agent's capabilities firsthand.
  * **[`agent-sft`](./agent-sft)**: Includes the training code, configurations, and instructions needed to reproduce ScaleCUA on the ScaleCUD dataset.

## ⚙️ Setup

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/OpenGVLab/ScaleCUA.git
    cd ScaleCUA
    ```
2.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

## 🎮 Playground

The Playground allows you to interactively experience the ScaleCUA agent's capabilities firsthand across Ubuntu, Android, and Web platforms. For a complete guide, please see the [[Playground]](playground/README.md).

Follow these two steps to begin:
1.  Deploy the ScaleCUA models with [vLLM](https://github.com/vllm-project/vllm) following our [[Model Deployment]](evaluation/README.md#-model-development). We support two modes of operation: **Native Agentic Model** using a single model for both UI grounding and planning, and **Agentic Workflow** supporting two different models for UI planning and grounding.

2. Set up your environment following [[Playground Environment]](playground/README.md#environment-configuration). We provide pre-configured, interactive virtual machines for Ubuntu, Android, and Web to simplify this process.

Now, you can try our agent in the interactive environment!


## 📊 Evaluation

We provide a suite of benchmarks for end-to-end agent evaluation using a vision-only setup. ScaleCUA support using **[vLLM](https://github.com/vllm-project/vllm)** to deploy and evaluate it through an OpenAI-compatible API. To run the evaluation benchmarks, please refer to the specific instructions within the [[Evaluation]](evaluation/README.md).

Our evaluation suite covers desktop, mobile, and web environments:

  * **Android**: `AndroidWorld`, `AndroidLab`
  * **Ubuntu**: `OSWorld`
  * **macOS**: `MacOSArena`
  * **Web**: `WebArenaLiteV2` (A refined version of WebArena-Lite suitable for visual-based agents)
  * **Windows**: `WindowsAgentArena`

## 🧠 Training

The directory `agent-sft/` contains all the necessary code and configuration files to train the ScaleCUA from scratch using our ScaleCUA-Data. We support training Computer Use Agents with both [InternVL](agent-sft/internvl_chat/README.md) and [Qwen-VL](agent-sft/qwen-vl-finetune/README.md).


## 💐 Acknowledgements
Thanks to the following open-sourced projects:

[OSWorld](https://github.com/xlang-ai/OSWorld) &#8194; 
[WindowAgentArena](https://github.com/microsoft/WindowsAgentArena) &#8194; 
[WebArena](https://github.com/web-arena-x/webarena) &#8194; 
[AndroidWorld](https://github.com/google-research/android_world)&#8194; 
[AGUVIS](https://github.com/xlang-ai/aguvis)&#8194; 
[MMBench-GUI](https://github.com/open-compass/MMBench-GUI) &#8194; 
[Qwen-VL](https://github.com/QwenLM/Qwen2.5-VL) &#8194; 
[InternVL](https://github.com/OpenGVLab/InternVL) &#8194;



## ⚖️ License

This project is licensed under the [Apache 2.0 License](https://www.google.com/search?q=LICENSE).

## 📜 Citation

If you find our work useful, please consider citing our paper:

```bibtex
@article{liu2025scalecua,
  title        = {ScaleCUA: Scaling Open-Source Computer Use Agents with Cross-Platform Data},
  author       = {Liu, Zhaoyang and Xie, Jingjing and Ding, Zichen and Li, Zehao and Yang, Bowen and Wu, Zhenyu and Wang, Xuehui and Sun, Qiushi and Liu, Shi and Wang, Weiyun and Ye, Shenglong and Li, Qingyun and Dong, Xuan and Yu, Yue and Lu, Chenyu and Mo, YunXiang and Yan, Yao and Tian, Zeyue and Zhang, Xiao and Huang, Yuan and Liu, Yiqian and Su, Weijie and Luo, Gen and Yue, Xiangyu and Qi, Biqing and Chen, Kai and Zhou, Bowen and Qiao, Yu and Chen, Qifeng and Wang, Wenhai},
  year         = {2025},
  note         = {Preprint},
  url          = {https://github.com/OpenGVLab/ScaleCUA}
}
```
