# 🌐WebArena-Lite-v2 基准评测指南

WebArena-Lite-v2 是一个真实可靠的基准测试，提供了一个更适合的框架，专门用于评估纯视觉GUI网络代理。作为对[WebArena-Lite](https://github.com/THUDM/VisualAgentBench)的改进，它提供了跨五种不同类型网站的154个任务，涵盖问答、页面内容匹配等多种任务模式，能够全面评测GUI智能体的各方位能力。我们感谢WebArena相关工作的杰出贡献。

## 📥评测前准备（下载镜像 + 加载镜像）

参考 [WebArena 仓库](https://github.com/web-arena-x/webarena/blob/main/environment_docker/README.md) 下载所需镜像。注意当前步骤仅需**下载**五个网站的六个镜像（Shopping、ShoppingAdmin、Reddit、Gitlab、OpenStreetMap），无需下载 Wikipedia 镜像，也无需创建容器。下载清单如下：

- 🛒Shopping 网站：`shopping_final_0712.tar`
- ⚙️ShoppingAdmin 网站：`shopping_admin_final_0719.tar`
- 💬Reddit 网站：`postmill-populated-exposed-withimg.tar`
- 🦊Gitlab 网站：`gitlab-populated-final-port8023.tar`
- 🗺️OpenStreetMap 网站：`openstreetmap-website-db.tar.gz`、`openstreetmap-website-web.tar.gz`

将这些镜像文件统一放置于一个文件夹下，修改 `launcher/01_docker_load_images.sh` 中的 `ARCHIVES_LOCATION` 为该文件夹路径，然后执行以下命令完成镜像加载：

```bash
bash launcher/01_docker_load_images.sh
```

## 🛠️配置运行环境

1. 执行 `pip install -r requirements.txt` 以安装全部 Python 依赖
2. 参考 [ScaleCUA Playground documentation](https://github.com/OpenGVLab/ScaleCUA/blob/main/playground/README.md) 文档 中的 Web 部分以配置可正常运行的 Web 交互环境

## 🚀开始评测

1. **环境初始化**：每次评测开始前，**必须重新进行环境初始化**
   - 在 `launcher/00_vars.sh` 中配置 Docker 容器启动参数，重要配置项如下：
     - `PUBLIC_HOSTNAME`：当前宿主机的IP地址，该IP地址需要支持被评测的服务器访问
     - `{WEBSITE}_PORT`：各评测网站的端口号，建议使用默认的 6666~6671 设置
     - `HTTP_PROXY/HTTPS_PROXY/NO_PROXY`：特别适用于 OpenStreetMap 网站的代理设置。若服务器无法正常连接外网，则需要设置此代理以访问 OpenStreetMap 的命名（nominatim）服务器。其余四个网站不需要外网即可正常运行。
   - 执行 `python launcher/start.py` 进行 Docker 初始化与任务实例化。

2. **配置文件设置**：需要配置两个文件
   - `config/agent/scalecua_agent.yaml`：参数含义在文件注释中已说明。推荐使用 `lmdeploy` 或 `vllm` 部署模型，通常只需修改 `base_url` 与 `model`（API 侧的模型名称）。
   - `config/env/web.yaml`：参数含义在文件注释中已说明，详情可查看 [ScaleCUA Playground 文档](https://github.com/OpenGVLab/ScaleCUA/blob/main/playground/README.md)。需将 `explicitly_allowed_ports` 列表修改为第一步中设置的各评测网站端口号，其余参数一般无需修改。

3. **执行评测**：提供一键启动脚本

   若需在 Docker 内执行则运行：

   ```bash
   bash start_scalecua_agent_evaluation_with_docker.sh
   ```

   若无需 Docker 则运行： 

   ```bash
   bash start_scalecua_agent_evaluation_wo_docker.sh
   ```

   启动脚本参数说明：

   - `--platform`: 可选项 web（Pure Web）/ ubuntu_web（Ubuntu Web），二者区别请参考 [ScaleCUA Playground文档](https://github.com/OpenGVLab/ScaleCUA/blob/main/playground/README.md)。目前 Ubuntu Web 的稳定性尚未确认，默认为 web。
   - `--env_config_path`：环境配置文件，默认为 `config/env/web.yaml`。
   - `--agent_config_path`: 代理模型配置文件，默认为 `native agent`模式的 `config/agent/scalecua_native_agent.yaml`，也可使用 `agentic workflow` 模式的 `config/agent/scalecua_agentic_workflow.yaml` 。
   - `--task_config_path`: 任务根目录，默认为 `tasks`。
   - `--num_workers`: 评测并行进程数，目前仅支持 web 平台的多进程并行，ubuntu web 平台目前不支持多进程并行评测，默认为 1。★**值得注意的是，任务间存在少量非正交性，任务执行顺序可能影响评估结果。我们建议采用串行执行以避免交互干扰。保持网站实例连续运行而非每次重启，主要考虑到Docker重启的时间成本及端口动态映射带来的复杂性。**
   - `--exp_name`: 实验名称，用于组织结果文件夹。
   - `--max_steps`: 模型执行的最大步数，默认为 15。

4. **评测结果**：将保存在 `results/{exp_name}` 文件夹下，包含各任务的独立文件夹 `results/{exp_name}/{task_id}`。其中 `results/{exp_name}/{task_id}/trajectory` 包含每一步截图，`results/{exp_name}/{task_id}/result.json` 包含任务完成情况。总评测结果位于 `results/{exp_name}/results.jsonl`。

## ✨特性

这个框架具有高度灵活性，作为我们[playground](https://github.com/OpenGVLab/ScaleCUA/blob/main/playground/)的扩展，支持：

- 自定义额外任务：你可以参考 `tasks` 文件夹和 `config/env/webarena/tasks` 文件夹进行额外的任务设置，甚至你可以将不同的Benchmark全部整合进该框架中。
- 自定义原生代理和代理工作流程：你可以在 `agents` 文件夹下自定义模型的 workflow，只需保证每一步返回正确格式的action即可。
- 自定义提示词：你可以在 `config/prompt_template` 文件夹下自由更改planning和grounding时所使用的提示词，对于ScaleCUA模型，最好使用我们提供的默认提示词。

## 🙏致谢

感谢 [WebArena](https://github.com/web-arena-x/webarena), [VisualAgentBench(WebArena-Lite)](https://github.com/THUDM/VisualAgentBench), [AgentS](https://github.com/simular-ai/Agent-S) 等精彩工作对GUI代理发展做出的贡献。
