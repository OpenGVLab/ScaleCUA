### Prepare Docker on linux(x86_64)

1. Install Docker on your machine. Make sure your machine already supports KVM. You can use the following code to check
   if your machine supports kvm:

```bash
apt-get install cpu-checker
kvm-ok
```

Meanwhile, ensure that your terminal has permission to start Docker. You can set it through the following code:

```bash
sudo usermod -aG docker $USER
newgrp docker
```

2. Download related docker files on link: https://drive.google.com/file/d/1SJ79gdO7whgUod3HnuS87aOKihRk1i-U/view?usp=drive_link

3. To create docker, run:

```bash
mkdir docker_file
cd docker_file
unzip /path/to/your/docker-file.zip
cd docker-file
docker build -t android_eval:latest .
```

Note that we use
```bash
RUN sed -i 's/deb.debian.org/mirrors.ustc.edu.cn/g' /etc/apt/sources.list
RUN pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple
```

to speed up download speed, you can replace it to your source if needed or just delete it.


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
  avd_name: Pixel_7_Pro_API_33
  avd_log_dir: ./logs/evaluation
  docker: True
  docker_args:
    image_name: android_eval:latest
    port: 6060
```

### Parameter Descriptions

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
- **avd_name**: The name of the AVD being used.
  - **Type**: String
  - **Example**: `"Pixel_7_Pro_API_33"`
  
- **avd_log_dir**: The directory where the AVD logs will be saved.
  - **Type**: String
  - **Example**: `"./logs/evaluation"`
  
- **docker**: Flag to indicate whether Docker is used for the evaluation. Need to set True.
  - **Type**: Boolean
  - **Example**: `true`
  
- **docker_args**: Arguments for configuring Docker.
  - **image_name**: The name of the Docker image to be used.
    - **Type**: String
    - **Example**: `"android-env:latest"`
    
  - **port**: The start port to be used for the Docker container.
    - **Type**: Integer
    - **Example**: `6060`
