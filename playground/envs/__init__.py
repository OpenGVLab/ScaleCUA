try:
    from envs.web.web_env import WebEnv
    from envs.web.ubuntu_web_env import UbuntuWebEnv
except:
    print("WebEnv not found, please install the required packages.")
try:
    from envs.android.android_env import AndroidEnv
except:
    print("AndroidEnv not found, please install the required packages.")
try:
    from envs.windows.windows_env import WindowsEnv
except:
    print("WindowsEnv not found, please install the required packages.")
try:
    from envs.ubuntu.ubuntu_env import UbuntuEnv
except:
    print("UbuntuEnv not found, please install the required packages.")
