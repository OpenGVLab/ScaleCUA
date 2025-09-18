# 📊 Evaluation Benchmarks for ScaleCUA Agent 🤖

This repository contains a suite of benchmarks for **end-to-end agent evaluations**. We test our trained models on a suite of offline and online GUI interaction benchmarks.

We employ a vision-only evaluation for all benchmarks, with models accessed via API.

## 🚀 Model Development
We use vLLM to deploy the series of ScaleCUA models. You can follow the [vLLM]() repository to complete the installation. Then use this command to deploy our model:

```
python -m vllm.entrypoints.openai.api_server --served-model-name ScaleCUA --model /path/to/ScaleCUA/checkpoint --limit-mm-per-prompt image=7 --port 10028 -tp 2
```

Once you run the command, the vLLM server starts, deploying your ScaleCUA model and making it accessible through an OpenAI-compatible API. To communicate with and get responses from this model, you need to know its specific "address." This is where the `model name`, `ip`, and `port` become essential.

- port: The port specifies the exact communication channel on the server that the model's API service is listening on. Since a single server can host multiple applications or services simultaneously, the port number acts as a unique identifier to ensure that incoming API requests are routed to the correct application—in this case, the vLLM model server.

- model name: The `model name` functions as a unique identifier for the specific model you wish to query on the server. An API server, such as the one provided by vLLM, is capable of hosting several different models simultaneously. This parameter is included within the body of the API request to tell the server precisely which of the available models should process the incoming prompt and generate a response.

- ip: The ip address, or hostname, serves to identify the specific machine on a network where the model is hosted, forming the base of the API endpoint's URL. By default, or when set to `localhost` (`127.0.0.1`), the service is only accessible from the same machine it is running on. To allow access from other computers, the server must be bound to a network-accessible address, allowing clients to connect using the machine's network IP.

### **Putting It All Together: Example API Call**

To call your model, you would send a POST request to the server's IP and port. The body of the request would be a JSON object specifying the `model name` and your prompt.

Here is an example using `curl` from the **same machine** where the model is running:

```bash
curl http://127.0.0.1:10028/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "scalecua",
    "messages": [
      {
        "role": "user",
        "content": [
          {
            "type": "text",
            "text": "What is in this image?"
          },
          {
            "type": "image_url",
            "image_url": {
              "url": "data:image/jpeg;base64,{your_base64_encoded_image}"
            }
          }
        ]
      }
    ],
    "max_tokens": 1024,
    "temperature": 0.2
  }'
```

In this command:

  * The URL `http://127.0.0.1:10028/v1/chat/completions` uses the **ip** (`127.0.0.1`) and **port** (`10028`).
  * The JSON data `"model": "scalecua"` specifies the **model name** you want to query.


## 📂 Directory Descriptions

These platforms collectively cover desktop, mobile, and web environments, enabling a thorough assessment of the agents’ capabilities in realistic and platform-specific usage scenarios.

- 📁 **AndroidWorld**, **AndroidLab**: Contains benchmarks for **online evaluations** in a Android environment based on [*AndroidWorld*](AnroidWorld/README.md) and [AndroidLab](AnroidLab/README.md).

- 📁 **MacOSArena**: Contains benchmarks for **online evaluations** in a macOS environment[*MacOSArena*](MacOSArena/README.md).

- 📁 **OSWorld**: Contains benchmarks for **online evaluations** in a Ubuntu environment based on [*OS-World*](OSWorld/README.md).

- 📁 **WebArenaLiteV2**: Contains benchmarks for **online evaluations** in a Web environment based on [*WebArenaLiteV2*](WebArenaLiteV2/README.md). See the special note below for more details.

- 📁 **WindowsAgentArena**: Contains benchmarks for **online evaluations** in a Windows environment based on [*WindowAgentArena*](WindowsAgentArena/README.md).

### 📝 Note on `WebArenaLiteV2`

It's worth noting that the WebArena series (e.g., WebArena, WebArena-Lite) was not originally designed for pure visual evaluation. Additionally, several tasks are either impossible to complete or require actions beyond the desktop environment.

To address these limitations, we refined WebArena-Lite and restructured its codebase into *WebArena-Lite-v2*, providing a more suitable framework for evaluating visual-based web agents.
