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

* First, start the vllm server using `bash scripts/t_cluster_scalecua_vllm_deploy.sh`
* Second, adjust the OPENAI_API_BASE and MODEL_NAME in `constants.py`
* Finally, run `python app.py`, maybe you need to set specified ip and port
