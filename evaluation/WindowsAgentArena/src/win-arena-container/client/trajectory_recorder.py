import datetime
import os
import json
import html as html_lib
import numpy as np
from typing import Dict, Any


class TrajectoryRecorder:
    def __init__(self, result_dir: str):
        self.result_dir = result_dir

    def save_dict(
        self, info_dict: Dict[str, Any], step_idx: int, action_timestamp: str
    ) -> dict:
        """
        Save each key of the observation to the specified path, parsing the correct datatypes.
        """
        file_format = "{key}-step_{step_idx}_{action_timestamp}.{ext}"
        obs_content = {k: None for k in info_dict.keys()}

        for key, value in info_dict.items():
            file_path = None
            if key in ["accessibility_tree", "user_question", "plan_result"]:
                file_path = os.path.join(
                    self.result_dir,
                    file_format.format(
                        key=key,
                        step_idx=step_idx,
                        action_timestamp=action_timestamp,
                        ext="txt",
                    ),
                )
                with open(file_path, "w") as f:
                    f.write(value if value else "No data available")
                obs_content[key] = os.path.basename(file_path)

            elif isinstance(value, bytes):
                file_path = os.path.join(
                    self.result_dir,
                    file_format.format(
                        key=key,
                        step_idx=step_idx,
                        action_timestamp=action_timestamp,
                        ext="png",
                    ),
                )
                with open(file_path, "wb") as f:
                    f.write(value)
                obs_content[key] = os.path.basename(file_path)

            elif isinstance(value, (int, float)):
                obs_content[key] = value

            elif (
                isinstance(value, (list, tuple, np.ndarray))
                and len(value) > 0
                and isinstance(value[0], (int, float))
            ):
                obs_content[key] = value

            elif isinstance(value, str):
                obs_content[key] = value

            elif isinstance(value, np.ndarray):
                file_path = os.path.join(
                    self.result_dir,
                    file_format.format(
                        key=key,
                        step_idx=step_idx,
                        action_timestamp=action_timestamp,
                        ext="npy",
                    ),
                )
                np.save(file_path, value)
                obs_content[key] = os.path.basename(file_path)

            elif "PIL" in str(type(value)):
                file_path = os.path.join(
                    self.result_dir,
                    file_format.format(
                        key=key,
                        step_idx=step_idx,
                        action_timestamp=action_timestamp,
                        ext="png",
                    ),
                )
                value.save(file_path)
                obs_content[key] = os.path.basename(file_path)

            elif isinstance(value, (dict, list)):
                file_path = os.path.join(
                    self.result_dir,
                    file_format.format(
                        key=key,
                        step_idx=step_idx,
                        action_timestamp=action_timestamp,
                        ext="json",
                    ),
                )
                with open(file_path, "w") as f:
                    json.dump(value, f)
                obs_content[key] = os.path.basename(file_path)

            else:
                obs_content[key] = f"key: {key}: {type(value)} not saved"

        return obs_content

    def dict_to_html(self, in_dict: Dict[str, Any], name: str) -> list:
        """Convert dictionary to HTML representation"""
        html = []

        def append_kv(key, value):
            ext = "txt" if not isinstance(value, str) else value.split(".")[-1]
            if ext not in ["png", "jpg", "jpeg", "txt"]:
                ext = "txt"
            value = str(value)
            is_path = "/" in value

            if key in ["user_question", "plan_result"]:
                is_path = False

            html.append("<details>")
            html.append(f"<summary>{key}</summary>")
            if is_path:
                html.append(f"<a href='{os.path.basename(value)}'>")
            if ext in ["png", "jpg", "jpeg"]:
                html.append(
                    f"<img style='max-width: 100%' src='{os.path.basename(value)}'/>"
                )
            elif ext in ["txt"]:
                html.append(f"<pre>\n{html_lib.escape(value)}\n</pre>")
            if is_path:
                html.append("</a>")
            html.append("</details>")

        html.append("<details>")
        html.append(f"<summary>{html_lib.escape(name)}</summary>")
        for key, value in in_dict.items():
            append_kv(key, value)
        html.append("</details>")
        return html

    def record_init(
        self, obs: Dict[str, Any], example: Dict[str, Any], init_timestamp: str
    ) -> None:
        """Record initial state"""
        init_dict = self.save_dict(obs, "reset", init_timestamp)

        # Save to JSONL
        with open(os.path.join(self.result_dir, "traj.jsonl"), "a") as f:
            traj_data = {
                "step_num": 0,
                "action_timestamp": init_timestamp,
                "action": None,
            }
            traj_data.update(init_dict)
            json.dump(traj_data, f)
            f.write("\n")

        # Save to HTML
        with open(os.path.join(self.result_dir, "traj.html"), "a") as f:
            f.write(self._get_html_header(example))
            html = []
            html.append(f"<pre>\n{example['instruction']}\n</pre>")
            html += self.dict_to_html(init_dict, "env.reset(config)")
            if obs_image := init_dict.get("screenshot", ""):
                html.append(
                    f"<img style='max-width: 100%' onclick='window.open(this.src, \"_blank\")' src='{obs_image}'/>"
                )
            else:
                html.append(f"<pre>No image</pre>")
            f.write("".join(html))

    def record_step(
        self,
        obs: Dict[str, Any],
        logs: Dict[str, Any],
        step_idx: int,
        action_timestamp: str,
        elapsed_timestamp: str,
        action: str,
        reward: float,
        done: bool,
        info: Dict[str, Any],
    ) -> None:
        """Record a single step"""
        obs_saved_content = (
            self.save_dict(obs, step_idx, action_timestamp) if obs else {}
        )
        logs_saved_content = (
            self.save_dict(logs, step_idx, action_timestamp) if logs else {}
        )

        # Save to JSONL
        with open(os.path.join(self.result_dir, "traj.jsonl"), "a") as f:
            traj_data = {
                "step_num": step_idx + 1,
                "action_timestamp": action_timestamp,
                "action": action,
                "reward": reward,
                "done": done,
                "info": info,
            }
            traj_data.update(obs_saved_content)
            traj_data.update(logs_saved_content)
            json.dump(traj_data, f)
            f.write("\n")

        # Save to HTML
        with open(os.path.join(self.result_dir, "traj.html"), "a") as f:
            html = []
            html.append(f"<h3>Step {step_idx + 1} ({elapsed_timestamp})</h3>")
            html += self.dict_to_html(
                {
                    **logs_saved_content,
                    "user_question": logs.get("user_question"),
                    "plan_result": logs.get("plan_result"),
                },
                "agent.predict(obs)",
            )
            html.append(f"<pre>\n{html_lib.escape(action)}\n</pre>")
            html += self.dict_to_html(obs_saved_content, "env.step(action)")
            if obs_image := obs_saved_content.get("screenshot"):
                html.append(
                    f"<img style='max-width: 100%' onclick='window.open(this.src, \"_blank\")' src='{obs_image}'/>"
                )
            else:
                html.append(f"<pre>No image</pre>")
            f.write("".join(html))

    def record_end(self, result: float, start_time: datetime.datetime) -> None:
        """Record final results"""
        with open(os.path.join(self.result_dir, "traj.html"), "a") as f:
            elapsed_timestamp = f"{datetime.datetime.now() - start_time}"
            f.write(f"<h1>Result: {result}</h1>")
            f.write(f"<h1>Elapsed Time: {elapsed_timestamp}</h1>")

    def _get_html_header(self, example: Dict[str, Any]) -> str:
        """Return HTML header with styling and theme selector"""
        return (
            """
<style>
    html { font-family: sans-serif; }
    summary { cursor: text; }
    details details>summary { padding-left: 0.5em; }
    #theme-selector { float: right; text-align: center; opacity: 0.5; }
    
    :root {
        --background-color: #ffffff;
        --text-color: #000000;
        --summary-hover: #f0f0f0;
        --summary-open: #ececec;
        --link-color: #1e90ff;
        --link-hover-color: #104e8b;
    }
    
    [data-theme='dark'] {
        --background-color: #000000;
        --text-color: #d4d4d4;
        --summary-hover: #1e1e1e;
        --summary-open: #1e1e1e;
        --link-color: #1e90ff;
        --link-hover-color: #63a4ff;
    }
    
    html, select {
        background: var(--background-color);
        color: var(--text-color);
    }
    summary:hover { background: var(--summary-hover); }
    details[open] > summary { background: var(--summary-open); }
    a { color: var(--link-color); }
    a:hover { color: var(--link-hover-color); }
    select { border: 1px solid var(--text-color); }
</style>
<details>
    <summary>config
        <select id='theme-selector' onchange='setTheme(this.value)'>
            <option value='' disabled selected>Theme</option>
            <option value='auto'>auto</option>
            <option value='light'>light</option>
            <option value='dark'>dark</option>
        </select>
        <script>
            function setTheme(theme) {
                if (theme === 'auto') {
                    document.documentElement.removeAttribute('data-theme');
                } else {
                    document.documentElement.setAttribute('data-theme', theme);
                }
            }
            (function() {
                const theme = localStorage.getItem('theme') || 'auto';
                document.getElementById('theme-selector').value = theme;
                setTheme(theme);
                document.getElementById('theme-selector').addEventListener('change', function() {
                    localStorage.setItem('theme', this.value);
                });
            })();
        </script>
    </summary>
    <pre>
"""
            + json.dumps(example, indent=2)
            + """
    </pre>
</details>"""
        )
