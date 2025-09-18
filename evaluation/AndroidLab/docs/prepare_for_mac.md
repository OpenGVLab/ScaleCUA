### Prepare AVD on mac(arm64)

1. Install Android Studio and ADB on your machine, and start a virtual machine to ensure that the adb command is properly installed. 
2. Download the avd.zip and ini files. Extract the avd.zip file and place it along with the ini file
   in `/Users/your user name/.android/avd`. Modify the ini file as follows:

```ini
avd.ini.encoding=UTF-8
path=/Users/your user name/.android/avd/Pixel_7_Pro_API_33.avd
path.rel=avd/Pixel_7_Pro_API_33.avd
target=android-33
```

If necessary, modify parts of the paths in the config.ini and hardware-qemu.ini files under `Pixel_7_Pro_API_33.avd` to
match your corresponding paths. The method for using the image has not been fully determined yet; a script will be
written once it stabilizes.

File download link: https://drive.google.com/file/d/19FnCaEh6VzR99Za-pvUoR-60iNe8mgom/view?usp=drive_link

Run the following code, then check in Android Studio -> Virtual Devices Manager to see if there is
a `Pixel_7_Pro_API_33` image and make sure it can start normally. However, please do not make any changes to the image.
Note to modify the avd and sdk paths to the correct paths.

```python
python tools/modify_mobile_to_avd.py 
    --avd_dir /Users/UserName/.android/avd 
    --sdk_dir /Users/UserName/Library/Android/sdk 
    --device_name Pixel_7_Pro_API_33
```

3. Configure the emulator

Run the following commands:

```bash
echo 'export ANDROID_SDK_HOME=/path/to/your/android/sdk' >> ~/.zshrc && source ~/.zshrc
echo 'export PATH=$PATH:/path/to/your/android/sdk/emulator' >> ~/.zshrc && source ~/.zshrc
```

If you are using bash instead of zsh, replace `~/.zshrc` with `~/.bash_profile`.

4. Create a yaml file in the project directory with the following content:

```yaml
agent:
    name: OpenAIAgent
    args:
        api_key: sk-
        api_base: ""
        model_name: "gpt-4-1106-preview"
        max_new_tokens: 512

task:
    class: TextOnlyMobileTask_AutoTest
    args:
        save_dir: "./logs/evaluation"
        max_rounds: 25
        request_interval: 3

eval:
    avd_base: /Users/your user name/.android/avd
    avd_name: Pixel_7_Pro_API_33_v2
    avd_log_dir: ./logs/avd
    android_sdk_path: /Users/your user name/Library/Android/sdk
```

Here, `/Users/your user name/.android/avd` is the default location where Android Studio stores images, `avd_name` is the
standard test image name, `avd_log_dir` is the directory for storing output results, and `android_sdk_path` is the
location of the Android SDK.

#### `agent`
- **name**: The name of the agent being used, must be declared in `agent/__init__.py`.
  - **Type**: String
  - **Example**: `"OpenAIAgent"`
  
- **args**: Arguments to configure the agent.
  - **api_key**: The API key for authenticating the agent.
    - **Type**: String
    
  - **api_base**: The base URL for the API endpoint.
    - **Type**: String
    
  - **model_name**: The name of the model to be used.
    - **Type**: String
    - **Example**: `"gpt-4o-mini-2024-07-18"`
    
  - **max_new_tokens**: The maximum number of new tokens the model can generate in one request.
    - **Type**: Integer
    - **Example**: `512`

#### `task`
- **class**: The class defining the type of task, must be declared in `evaluation/auto_test.py`. For basic evaluation, we use `"TextOnlyMobileTask_AutoTest"` for XML mode and `"ScreenshotMobileTask_AutoTest"`for SoM mode. 
  - **Type**: String
  - **Example**: `"TextOnlyMobileTask_AutoTest"`
  
- **args**: Arguments to configure the task.
  - **save_dir**: The directory where the evaluation logs will be saved.
    - **Type**: String
    - **Example**: `"./logs/evaluation"`
    
  - **max_rounds**: The maximum number of rounds for the task. default to be 25.
    - **Type**: Integer
    - **Example**: `25`
    
  - **request_interval**: The interval between requests, in seconds. default to be 3.
    - **Type**: Integer
    - **Example**: `3`
    
  - **mode**: The mode of operation. default to be `"in_app"`.
    - **Type**: String
    - **Example**: `"in_app"`

#### `eval`
- **avd_base**: The base directory for Android Virtual Device (AVD) configurations.
  - **Type**: String
  - **Example**: `"/Users/your user name/.android/avd"`
  
- **avd_name**: The name of the AVD being used.
  - **Type**: String
  - **Example**: `"Pixel_7_Pro_API_33"`
  
- **avd_log_dir**: The directory where the AVD logs will be saved.
  - **Type**: String
  - **Example**: `"./logs/evaluation"`
  
- **android_sdk_path**: The file path to the Android SDK.
  - **Type**: String
  - **Example**: `"/Users/your user name/Library/Android/sdk"`
  
- **show_avd**: Flag to determine whether the AVD should be displayed or hided. default to be False.
  - **Type**: Boolean
  - **Example**: `false`