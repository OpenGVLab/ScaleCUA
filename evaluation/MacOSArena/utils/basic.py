from pathlib import Path
from utils.logger import ProjectLogger
from typing import List

import re
import ast
import astor


# script_dir = Path(__file__).resolve().parent

# Logger setup
logger = ProjectLogger()


# for debug only
def fetch_screenshot(env, local_save_path: str = "./screenshot.png"):
    remote_tmp_path = "/tmp/fullscreen_dock.png"

    capture_cmd = f"sudo screencapture -C {remote_tmp_path}"

    env.connect_ssh()
    try:
        logger.info("Executing screencapture command in macOS...")
        stdout, stderr = env.run_command(capture_cmd, decode=False)

        out = stdout.read().decode().strip()
        err = stderr.read().decode().strip()
        # logger.debug(f"[stdout] {out}")
        # logger.debug(f"[stderr] {err}")

        logger.info(f"Fetching screenshot to {local_save_path}")
        Path(local_save_path).parent.mkdir(parents=True, exist_ok=True)
        env.connect_sftp()
        env.sftp_client.get(remote_tmp_path, local_save_path)

        logger.info("Screenshot successfully captured and saved.")
    except Exception as e:
        logger.error(f"Screenshot capture failed: {e}")


class ActionTransformer(ast.NodeTransformer):
    def visit_Expr(self, node):
        if isinstance(node.value, ast.Call):
            return self.replace_pyautogui_call(node.value) or node
        return node

    def replace_pyautogui_call(self, call_node):
        if not isinstance(call_node.func, ast.Attribute):
            return None
        func = call_node.func
        if not (isinstance(func.value, ast.Name) and func.value.id == "pyautogui"):
            return None

        if func.attr in {"write", "typewrite"}:
            return self.transform_write(call_node)
        elif func.attr == "doubleClick":
            return self.transform_doubleclick(call_node)
        return None

    def transform_write(self, node):
        message_expr = None
        for kw in node.keywords:
            if kw.arg == "message":
                message_expr = kw.value
                break
        if message_expr is None and node.args:
            message_expr = node.args[0]
        if message_expr is None:
            return node

        return ast.Expr(
            value=ast.Call(
                func=ast.Attribute(
                    value=ast.Name(id="keyboard", ctx=ast.Load()),
                    attr="write",
                    ctx=ast.Load(),
                ),
                args=[message_expr],
                keywords=[ast.keyword(arg="delay", value=ast.Constant(value=0.1))],
            )
        )

    def transform_doubleclick(self, node):
        x = y = None
        if len(node.args) >= 1:
            x = node.args[0]
        if len(node.args) >= 2:
            y = node.args[1]
        for kw in node.keywords:
            if kw.arg == "x":
                x = kw.value
            elif kw.arg == "y":
                y = kw.value

        new_nodes = []

        if x and y:
            move_expr = ast.Expr(
                value=ast.Call(
                    func=ast.Attribute(
                        value=ast.Name(id="pyautogui", ctx=ast.Load()),
                        attr="moveTo",
                        ctx=ast.Load(),
                    ),
                    args=[x, y],
                    keywords=[],
                )
            )
            new_nodes.append(move_expr)

        click_expr = ast.Expr(
            value=ast.Call(
                func=ast.Attribute(
                    value=ast.Call(
                        func=ast.Attribute(
                            value=ast.Attribute(
                                value=ast.Name(id="pynput", ctx=ast.Load()),
                                attr="mouse",
                                ctx=ast.Load(),
                            ),
                            attr="Controller",
                            ctx=ast.Load(),
                        ),
                        args=[],
                        keywords=[],
                    ),
                    attr="click",
                    ctx=ast.Load(),
                ),
                args=[],
                keywords=[
                    ast.keyword(
                        arg="button",
                        value=ast.Attribute(
                            value=ast.Attribute(
                                value=ast.Name(id="pynput", ctx=ast.Load()),
                                attr="mouse",
                                ctx=ast.Load(),
                            ),
                            attr="Button.left",
                            ctx=ast.Load(),
                        ),
                    ),
                    ast.keyword(arg="count", value=ast.Constant(value=2)),
                ],
            )
        )

        new_nodes.append(click_expr)

        return new_nodes


def transform_pyautogui_line(line):
    try:
        tree = ast.parse(line)
        new_tree = ActionTransformer().visit(tree)
        ast.fix_missing_locations(new_tree)
        if isinstance(new_tree, list):
            return "\n".join(astor.to_source(stmt).rstrip() for stmt in new_tree)
        return astor.to_source(new_tree).rstrip()
    except Exception:
        return line


def reset_applications(env, application_list: List[str]):
    # Add application reset logic if required by the evaluation strategy.
    # Some evaluation tasks may depend on a clean or known initial application state.
    from evaluators.getter import (
        clock_reset_window_status,
        settings_reset_window_status,
        terminal_reset_window_status,
    )

    if "terminal" in application_list:
        terminal_reset_window_status(env)
    if "mac_system_settings" in application_list:  # should strictly be the last one
        settings_reset_window_status(env)
    if "clock" in application_list:  # should strictly be the last one
        clock_reset_window_status(env)
    # TODO: deal with the situations that both clock and settings in application_list
    pass
    # import pyautogui
    # pyautogui.
