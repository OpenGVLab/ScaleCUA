# How to modify the Androidlab

## How to Modify the Backbone Model

The `Agent` class has been predefined in the `agent/` folder, with implementations for the OpenAI interface based on
oneapi and the currently deployed GLM interface. If you need to add a base model, you need to:

1. Create a new Python file under the `agent/` directory, and refer to `agent/model/OpenAIAgent`. Implement your model call by inheriting the `Agent` class. The `act` function input is already organized according to the OpenAI message format, and the output should be a string. If the input format of the corresponding model differs from OpenAI, you can refer to the `format_history` function in `claude_model` and the `prompt_to_message` function in `qwen_model` for modifications. `format_history` can organize the format of historical records, and the `prompt_to_message` method converts the prompt and image input (if any) of the current turn into the single-turn format of the current model.
2. Import your new class in `agent/__init__.py`.
3. Replace the content under `agent` in the config file used by `eval.py` with:

```yaml
agent:
    name: Your Agent Module Name
    args:
        max_new_tokens: 512
```

Make sure the name matches your implemented class name, and the content under `args` will be passed to your
class's `init` function.

## Steps to Add a New Task

During the process of writing a new task, it is equally important to write and use the code to determine if your code is
correct through actual running results. Therefore, please follow the steps below to ensure each new task is error-free.

1. Write your task. Tasks include yaml files, evaluation methods, and corresponding mobile app installation.
    1. The task's yaml file should refer to other existing files under `evaluation/config` and must
       include `task_id`, `task`, `metric_type`, and `metric_func`. `adb_query` is only used when the results need to be
       queried using adb commands. Although `category` is not yet in use, it is strongly recommended to add it.
    2. The evaluation method needs to inherit the `evaluation/task/SingleTask` class. After each recorded operation,
       the `judge` function will be executed, and its return value is a
       dict: `{"judge_page": bool, "1": bool, ..., "complete": bool}`. The code will record the judgment result of the
       last page where `judge_page` is `True`, and `complete` should only be set to `True` if all judgment points are
       correct. If it's a task that compares return values, the `check_answer` method has already been implemented.
       Modify `final_ground_truth` to the standard answer before calling this function.
    3. Refer to other tasks, import all evaluation methods in `evaluation/app_name/__init__.py` into the `function_map`
       class.
    4. To ensure the model can execute the launch command correctly, add the app name and corresponding package name
       in `templates/packages/apps_dict`. The package name can be obtained by
       executing `adb -s {device} shell dumpsys window | grep mCurrentFocus | awk -F '/' '{print $1}' | awk '{print $NF}'`.
2. Execute your task using at least the most advanced agent and generate evaluation results. If necessary, quickly
   complete the correct operation during model operation intervals to ensure that the recorded operation can capture the
   correct result page between two model operations to test if your code can complete the detection task.
3. Use the `tools/check_result_multiprocess.py` function to generate screenshots of each step. Focus on checking whether
   the screenshots of correct model operations are indeed judged as correct.

## Steps to Change AVD Snapshot

If you want to define a mobile snapshot different from the android eval snapshot, you need to follow these steps:

1. Download related docker files from the
   link: https://drive.google.com/file/d/1xpPEzVof5hrt5bQY6BHm_4Uoyq5mJQNb/view?usp=drive_link
2. Extract the file, enter the extracted folder, and then run:

```bash
docker build -t android_eval_no_avd:latest .
```

3. Configure your AVD snapshot on an x86_64 machine (it is recommended to configure it directly using Android Studio).
   Note that the default installed Android AVD type is:

```dockerfile
RUN /bin/bash -c "source /root/.bashrc && yes | sdkmanager 'platform-tools' 'emulator' 'system-images;android-33;google_apis;x86_64'"
RUN /bin/bash -c "source /root/.bashrc && yes | sdkmanager 'build-tools;33.0.0'"
RUN /bin/bash -c "source /root/.bashrc && yes | sdkmanager 'platforms;android-33'"
```

If you want to configure the AVD for a different version, please modify the specific version number installed in the
Dockerfile. Note that the version number must be strictly consistent, otherwise, the installed image will not be able to
read the existing cache.

4. You can use the following code to generate the AVD image used in the docker:

```python
python tools/modify_mobile_to_docker.py 
    --avd_dir /Path/to/your/.android/avd 
    --device_name your device name 
    --save_dir /Path/to/your/save/avd
```

Alternatively, you can modify it as follows:

Find your .avd folder and .ini file through Android Studio -> Virtual Devices Manager -> Right-click -> Show on Disk,
and make the following modifications:

In Pixel_7_Pro_API_33.ini, modify path and path.rel to the following paths:

```ini
avd.ini.encoding=UTF-8
path=/root/.android/avd/device name.avd
path.rel=avd/device name.avd
target=android-33
```

In Pixel_7_Pro_API_33.avd/config.ini, modify the following paths:

```ini
...
image.sysdir.1 = system-images/android-33/google_apis/x86_64/
...
skin.path = /root/.android/skins/pixel_7_pro
...
```

Keep the other contents unchanged.

5. Start an image and copy your .avd folder and .ini file into the image:

```bash
docker run -it  android_eval_no_avd:latest /bin/bash 
docker cp /path/to/your/device name.avd container_id:/root/.android/avd
docker cp /path/to/your/device name.ini container_id:/root/.android/avd
```

After completing the above, you can execute the following in the image:

```bash
emulator -avd device name -no-window -no-audio -no-snapshot-save
```

Verify whether the installation is successful.