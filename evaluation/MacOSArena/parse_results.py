import json
from pathlib import Path
import numpy as np

def calculate_EQA(success_per_task, step_per_task, predefined_order, max_steps=15):
    assert len(step_per_task) == len(predefined_order)
    assert len(success_per_task) == len(predefined_order)

    
    order = [predefined_order[idx] for idx in sorted(predefined_order)]

    try:
        steps = np.array([step_per_task[tid] for tid in order], dtype=float)
        succ = np.array([success_per_task[tid] for tid in order], dtype=float)
    except KeyError as e:
        raise KeyError(f"Task ID {e.args[0]} missing in success_per_task or step_per_task.")

    S_tot = succ.sum()
    if S_tot == 0:
        return 0.0

    total_max_steps = max_steps * len(predefined_order)
    cum_steps = np.cumsum(steps)
    cum_steps = np.clip(cum_steps, None, total_max_steps)
    u = cum_steps / total_max_steps
    recall = np.cumsum(succ) / len(predefined_order)

    u = np.hstack(([0.0], u))
    recall = np.hstack(([0.0], recall))

    grid = np.linspace(0, 1, 101)
    recall_at_grid = np.interp(grid, u, recall)

    return float(np.mean(recall_at_grid))


def analyze_results(result_root: str):
    result_root = Path(result_root)
    result_files = list(result_root.glob("**/result.txt"))

    total_tasks = 0
    success_count = 0
    total_steps = 0
    success_15_count = 0
    capped_steps_total = 0

    success_cases = {}
    success_per_task = {}
    step_per_task = {}
    predefined_order = {}

    success_per_task_15 = {}
    step_per_task_15 = {}

    for idx, result_file in enumerate(sorted(result_files)):
        try:
            with open(result_file, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            print(f"[WARN] Failed to read {result_file}: {e}")
            continue

        total_tasks += 1
        steps = data.get("steps_used", 0)
        completed = data.get("completed", False)
        total_steps += steps
        capped_steps_total += min(15, steps)

        try:
            relative_path = result_file.relative_to(result_root)
            task_name = str(relative_path.parent)
        except:
            task_name = str(result_file)

        success_per_task[task_name] = int(completed)
        step_per_task[task_name] = steps
        predefined_order[idx] = task_name

        step_per_task_15[task_name] = min(15, steps)
        success_per_task_15[task_name] = int(completed and steps <= 15)

        if completed:
            success_count += 1
            success_cases[task_name] = steps
            if steps <= 15:
                success_15_count += 1
                
    success_rate = success_count / total_tasks if total_tasks else 0
    steps_used_avg = total_steps / total_tasks if total_tasks else 0
    success_15_steps_rate = success_15_count / total_tasks if total_tasks else 0
    steps_used_avg_as_15 = capped_steps_total / total_tasks if total_tasks else 0

    eqa_15 = calculate_EQA(success_per_task_15, step_per_task_15, predefined_order, max_steps=15)
    eqa_50 = calculate_EQA(success_per_task, step_per_task, predefined_order, max_steps=50)

    result_summary = {
        "task num": total_tasks,
        "success rate": round(success_rate, 4),
        "steps_used_avg": round(steps_used_avg, 2),
        "success_15_steps_rate": round(success_15_steps_rate, 4),
        "steps_used_avg_as_15_steps": round(steps_used_avg_as_15, 2),
        "EQA@15": round(eqa_15, 4),
        "EQA@50": round(eqa_50, 4)
    }

    with open(result_root / "final.txt", "w", encoding="utf-8") as f:
        json.dump(result_summary, f, indent=2)
    with open(result_root / "success_cases.json", "w", encoding="utf-8") as f:
        json.dump(success_cases, f, indent=2)

    print("=== Result Summary ===")
    for key, value in result_summary.items():
        print(f"{key}: {value}")
    print(f"\n✅ Summary saved to: {result_root/'final.txt'}")
    print(f"✅ Success cases saved to: {result_root/'success_cases.json'}")

    return result_summary

if __name__ == "__main__":
    # analyze_results("/nvme/wuzhenyu/results/gpt-4o-uground7b/multi_task")
    # analyze_results("/nvme/wuzhenyu/results/uitars72bdpo/single_task")
    # analyze_results("/nvme/wuzhenyu/results/Aguvis-72B-720P/single_task")
    # analyze_results("/nvme/wuzhenyu/results/gpt-4o-ui_tars_15_7b/single_task")
    # analyze_results("/nvme/wuzhenyu/results/ui_tars_15_7b/single_task")
    # analyze_results("/nvme/wuzhenyu/results/gpt-4o/sinlge_task")
    # analyze_results("/nvme/wuzhenyu/results/gpt-4o/multi_task")
    # analyze_results("/nvme/wuzhenyu/results/gpt-4o-uground7b/single_task")
    # analyze_results("/nvme/wuzhenyu/results/claude-3-7-sonnet-20250219/single_task")
    
    # analyze_results("/nvme/wuzhenyu/results/gpt-4o-uground7b/multi_task")
    # analyze_results("/nvme/wuzhenyu/results/gpt-4o/multi_task")
    # analyze_results("/nvme/wuzhenyu/results/gpt-4o-ui_tars_15_7b/multi_task")
    # analyze_results("/nvme/wuzhenyu/results/uitars72bdpo/multi_task")
    # analyze_results("/nvme/wuzhenyu/results/Aguvis-72B-720P/multi_task")
    # analyze_results("/nvme/wuzhenyu/results/ui_tars_15_7b/multi_task")
    # analyze_results("/nvme/wuzhenyu/results/claude-3-7-sonnet-20250219/multi_task")
    
    # analyze_results("/nvme/wuzhenyu/results/uitars72bdpo/single_task")
    # analyze_results("/nvme/wuzhenyu/results/gpt-4o/single_task")
    # analyze_results("/nvme/wuzhenyu/results/gpt-4o-ui_tars_15_7b/single_task")
    # analyze_results("/nvme/wuzhenyu/results/ui_tars_15_7b/single_task")
    # analyze_results("/nvme/wuzhenyu/results/Aguvis-72B-720P/single_task")
    # analyze_results("/nvme/wuzhenyu/results/gpt-4o-uground7b/single_task")
    # analyze_results("/nvme/wuzhenyu/results/claude-3-7-sonnet-20250219/single_task")
    
    # analyze_results("/nvme/wuzhenyu/results/gui_v93/multi_task")
    # analyze_results("/nvme/wuzhenyu/results/gui_v93/single_task")
    # analyze_results("/nvme/wuzhenyu/results/gui_v91/multi_task")
    # analyze_results("/nvme/wuzhenyu/results/gui_v91/single_task")
    # analyze_results("/nvme/wuzhenyu/results/gui_v108/multi_task")
    # analyze_results("/nvme/wuzhenyu/results/gui_v108/single_task")
    analyze_results("/nvme/wuzhenyu/results/simple_qwenvl/single_task")
    analyze_results("/nvme/wuzhenyu/results/simple_qwenvl/multi_task")