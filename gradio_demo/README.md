---
title: ScaleCUA
emoji: ⚡
colorFrom: yellow
colorTo: gray
sdk: gradio
sdk_version: 4.36.1
app_file: app.py
pinned: false
license: mit

---

* First, start the vllm server using `bash scripts/srun_scalecua_vllm_deploy.sh` or `bash scripts/scalecua_vllm_deploy.sh`
* Then, run `python app.py --model-worker-url http://0.0.0.0:10024`.  You may need to set specified ip and port.
