# Android Environment API

This project provides a FastAPI‑based HTTP interface for spinning up and controlling an Android environment (emulator or physical device) to facilitate model testing.

## Features

- Launch and manage Android Virtual Devices (AVDs) or connect to physical devices via ADB  
- Expose REST endpoints for common operations (screenshot, input events, recording, etc.)  
- Lightweight Docker setup for easy deployment  
- Native server installation option for full flexibility

## Prerequisites

- Python 3.11
- [FastAPI](https://fastapi.tiangolo.com/)  
- [Uvicorn](https://www.uvicorn.org/)  

## Environment Configuration Options

You can set up your Android environment in **either** of the following ways (no particular order):

- **Docker‑based Emulator**  
  1. **Install Docker**  
     ```bash
     # Follow your OS guide:
     https://docs.docker.com/engine/install/
     ```  
  2. **Prepare the AVD Docker image**  
     - Based on [THUDM/Android-Lab](https://github.com/THUDM/Android-Lab) with minor tweaks in our `Dockerfile`.  
     - See [here](docs/prepare_for_linux.md) for full instructions.  
  3. **(Optional) Customize AVD**  
     - Modify system images or device configs by referencing the [THUDM/Android-Lab](https://github.com/THUDM/Android-Lab)’s manual.  

- **Local VM or Physical Device**  
  1. **Install Android SDK & ADB**  
     (See https://developer.android.com/tools)  
  2. **Option A: Local VM**  
     - Install [Android Studio](https://developer.android.com/studio/intro)  
     - Create or download an AVD in AVD Manager → note the AVD name.  
  3. **Option B: Physical Device**  
     - Enable Developer Mode & USB Debugging on your device.  
     - Connect via USB, then verify:  
       ```bash
       adb devices
       ```
     - Approve the host fingerprint on the device when prompted.

## Running the API Server

Once your Android emulator or device is up and reachable:

```bash
cd env_api
uvicorn env_api_launch:app --host 0.0.0.0 --port <PORT>
````

Replace `<PORT>` with your chosen port (e.g., `8000`).
The interactive API docs will be at `http://<SERVER_IP>:<PORT>`.

## References

* Docker: [https://docs.docker.com/engine/install/](https://docs.docker.com/engine/install/)
* Android‑Lab prep: `docs/prepare_for_linux.md` (based on [https://github.com/THUDM/Android-Lab](https://github.com/THUDM/Android-Lab))
* Android SDK tools: [https://developer.android.com/tools](https://developer.android.com/tools)
* Android Studio: [https://developer.android.com/studio/intro](https://developer.android.com/studio/intro)
