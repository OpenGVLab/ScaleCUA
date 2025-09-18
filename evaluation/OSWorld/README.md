# Installation
1. Install the necessary packages. For more detailed installation instructions, please refer to [OSWorld](https://github.com/xlang-ai/OSWorld).
```
# python >= 3.9
pip install -r requirements.txt
pip install desktop-env
```
2. Install Docker using the official instructions for your operating system. To verify the installation, run `docker -v`. If it shows the version, it has been installed correctly.

# Evaluation
1. Deploy the [ScaleCUA]() models with our [guidence](../README.md#-model-development), and then record the model name and URL.
2. In `eval.sh`, replace the values for --url_set and --model with your actual model URL and name, respectively.
3. Start the evaluation using `bash eval.sh results/scalecua_3b_50step 2`. 
  ```
  #!/bin/bash
  
  # =================================================================
  # Script to run the multi-environment CUA agent.
  #
  # Usage:
  #   bash your_script_name.sh <results_directory> <num_environments>
  #
  # Example:
  #   bash your_script_name.sh ./results 16
  # =================================================================
  
  # $1: The first command-line argument, specifying the path to the results directory.
  RESULT_DIR=$1
  
  # $2: The second command-line argument, defining the number of parallel environments to run.
  NUM_ENVS=$2
  
  # Create the results directory. The -p flag ensures parent directories are also created if they don't exist.
  mkdir -p ${RESULT_DIR}
  
  # Execute the main Python program
  python run_multienv_cua.py \
      --path_to_vm docker_vm_data/Ubuntu.qcow2 \
      --headless \
      --action_space pyautogui \
      --observation_type screenshot \
      --screen_width 1920 \
      --screen_height 1080 \
      --sleep_after_execution 2.0 \
      --max_steps 50 \
      --max_trajectory_length 100 \
      --temperature 0.0 \
      --top_p 0.9 \
      --max_tokens 1000 \
      --result_dir ${RESULT_DIR} \
      --num_envs ${NUM_ENVS} \
      --model scalecua \
      --url_set http://10.140.66.46:10029/v1,http://10.140.66.27:10025/v1 \
      2>&1 | tee -a ${RESULT_DIR}/run.log
  ```
4. Show result for each domain.
```
python show_result.py --result_folder results/scalecua_3b_50step --model_name MODEL_NAME_IN_EVAL.SH
```

# Acknowledgement
This repository is based on [OSWorld](https://github.com/xlang-ai/OSWorld). We have integrated ScaleCUA into its framework. Thanks for the excellent work.
