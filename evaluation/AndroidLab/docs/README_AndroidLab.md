# AndroidLab: Training and Systematic Benchmarking of Android Autonomous Agents

<p align="center">
   <a href="https://arxiv.org/abs/2410.24024" target="_blank">📃 Paper </a>
</p>

Chinese version of this README is available [here](README_CN.md).

We develop a systematic Android agent framework，named AndroidLab. It includes an operation environment and a reproducible benchmark. AndroidLab benchmark includes predefined Android virtual devices and 138 tasks across nine apps built on these devices. 

This repository is the code framework for the operation environment and
 benchmark section. We provide two execution modes: AVD on Mac (arm64) and Docker on Linux (x86_64). You can freely add or modify new tasks or Android images according to our framework. We offer a complete evaluation framework that can be used to assess the performance of various Android agents.

We have also open-sourced the Android Instruct dataset mentioned in the paper. Please refer to [here](docs/instruction_tuning.md) for more details.



![](./assets/main-picture.png)

# Benchmark Components

In our experiment, we utilized a range of apps to conduct various tests. The following mobile apps are chosen:

- **Bluecoins**: A personal finance management app used for tracking expenses and income.
- **Calendar**: A calendar app helps in organizing schedules and setting reminders.
- **Cantook**: An e-book reader for storing, managing, and reading e-books.
- **Clock**: A clock app for displaying the time, setting alarms, and using a stopwatch.
- **Contacts**: A contact management app for storing and organizing contact information.
- **Maps.me**: An offline map app for navigation and exploring locations.
- **PiMusic**: A music player app for organizing and playing locally stored music files.
- **Settings**: A settings app for configuring device settings and preferences.
- **Zoom**: A video conferencing app for hosting and joining online meetings.

The selection of these apps underwent multiple iterations to ensure their suitability for our evaluation purposes. A key criterion for the final selection was that each app must function independently, without requiring an internet connection or user account login. This ensures that the evaluations can be consistently replicated under the same conditions, eliminating external dependencies and reducing the risk of privacy breaches. Consequently, this approach maintains the reliability and reproducibility of our results.

![](./assets/avd-subgoal-subcates.png)
# Leaderboard

Main Result of XML and SoM modes. SR, Sub-SR, RRR, and ROR stand for Success Rate, Sub-Goal Success Rate, Reversed Redundancy Ratio, and Reasonable Operation Ratio, respectively. For all these metrics, a higher value means better. **-ft** represents an instruction tuning model. In each mode, **Bold** represents the best result.

![](./assets/leaderboard.png)

By using the Android Instruct dataset, we trained six open-source text-only and multimodal models, achieving an average success rate from 4.59% to 21.50% for LLMs and from 1.93% to 13.28% for LMMs. respectively, reaching a performance level comparable to proprietary models.

![](./assets/before-after-sft.png)


# Quick start

## Auto Evaluation Pipeline

We offer two testing methods: AVD on Mac (arm64) and Docker on Linux (x86_64).

### Prerequisites

Clone this repo and install the dependencies.

```bash
cd /path/to/your/repo
conda create -n Android-Lab python=3.11
conda activate Android-Lab
pip install -r requirements.txt
```

If you use AVD on Mac (arm64), please refer to [here](docs/prepare_for_mac.md) to set up the environment.

If you use Docker on Linux (x86_64), please refer to [here](docs/prepare_for_linux.md) to set up the environment.

### Run the Auto Evaluation Pipeline

To test, run:

```bash
python eval.py -n test_name -c your path to config.yaml
```

The specific output of each question is saved under `./logs/evaluation/test_name`, and the evaluation results are saved
in the `output` folder.
If you only want to run a few questions for testing, you can refer to:

```bash
python eval.py -n test_name -c your path to config.yaml --task_id taskid_1,taskid_2,taskid_3
```

We support parallel testing. Please note that you need to confirm in advance that
you have sufficient memory and storage. Each concurrent session takes up approximately 6G of memory and 9G of storage
space.

```bash
python eval.py -n test_name -c your path to config.yaml -p 3
```

The corresponding task_id for each question can be found in `evaluation/config`.

Use the following code to generate evaluation results:

```bash
# eval by gpt-4o-2024-05-13:
export OPENAI_API_KEY='your-api-key-here'
python generate_result.py --input_folder ./logs/evaluation/ --output_folder ./logs/evaluation/ --output_excel ./logs/evaluation/test_name.xlsx --judge_model gpt-4o-2024-05-13

# eval by glm4:
python generate_result.py --input_folder ./logs/evaluation/ --output_folder ./logs/evaluation/ --output_excel ./logs/evaluation/test_name.xlsx --judge_model glm4 --api_key your api key
```

You need to fill in your judge model and api_key(may be api_base, too). We now support gpt-4o-2024-05-13 and glm4.
generate_result.py will generate an Excel file of all test results under --input_ir, containing detailed results for each question.

If you want to do further development based on Androidlab, including changing the agent's base model, adding tasks, and changing the AVD image, please refer to:[here](docs/modify_androidlab.md)

# Citation

```
@misc{xu2024androidlabtrainingsystematicbenchmarking,
      title={AndroidLab: Training and Systematic Benchmarking of Android Autonomous Agents}, 
      author={Yifan Xu and Xiao Liu and Xueqiao Sun and Siyi Cheng and Hao Yu and Hanyu Lai and Shudan Zhang and Dan Zhang and Jie Tang and Yuxiao Dong},
      year={2024},
      eprint={2410.24024},
      archivePrefix={arXiv},
      primaryClass={cs.AI},
      url={https://arxiv.org/abs/2410.24024}, 
}
```
