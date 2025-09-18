import os
import json
import cv2
import jsonlines
import numpy as np
import argparse


def create_video(frames_actions, out_path, fps):
    if not frames_actions:
        print("No screenshots found for video.")
        return

    # Read the first image to get the size
    first_image = cv2.imread(frames_actions[0][0])
    if first_image is None:
        print(f"Error reading the first image {frames_actions[0][0]}")
        return

    height, width, _ = first_image.shape

    # Define the codec and create VideoWriter object
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(out_path, fourcc, fps, (width, height))

    for img_path, action, instruction in frames_actions:
        img = cv2.imread(img_path)
        if img is not None:
            overlay = img.copy()
            lines = f"Instruction: {instruction}\nAction: {action}".split("\n")
            line_height = 30
            num_lines = len(lines)
            box_height = num_lines * line_height + 10

            # Draw a black box behind the text
            cv2.rectangle(
                overlay, (0, height - box_height), (width, height), (0, 0, 0), -1
            )

            # Add instruction and action text
            for i, line in enumerate(lines):
                y = height - box_height + 30 + i * line_height
                cv2.putText(
                    overlay,
                    line,
                    (10, y),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    (255, 255, 255),
                    2,
                )

            # Blend the overlay with the original image
            alpha = 0.7
            img = cv2.addWeighted(overlay, alpha, img, 1 - alpha, 0)

            out.write(img)
        else:
            print(f"Error reading image {img_path}")

    out.release()
    print(f"Video saved to {out_path}")


def process_task(task_folder, out_path, fps):
    traj_path = os.path.join(task_folder, "traj.jsonl")
    if not os.path.exists(traj_path):
        print(f"File {traj_path} does not exist.")
        return

    frames_actions = []

    with jsonlines.open(traj_path) as reader:
        for line in reader:
            if "screenshot" in line and "action" in line and "instruction" in line:
                # frames_actions.append((line['screenshot'], line['action'], line['instruction']))
                frames_actions.append(
                    (
                        os.path.join(task_folder, os.path.basename(line["screenshot"])),
                        line["action"],
                        line["instruction"],
                    )
                )

    if not frames_actions:
        print(f"No screenshots found in {traj_path}")
        return

    # Create a video from the collected screenshot paths
    create_video(frames_actions, out_path, fps)


def process_tasks(results_dir, action_space, obs_type, model_name, run_id, fps):
    experiment_dir = os.path.join(
        results_dir, action_space, obs_type, model_name, run_id
    )
    if not os.path.exists(experiment_dir):
        print("New experiment, no result yet.")
        return None

    for domain in os.listdir(experiment_dir):
        domain_path = os.path.join(experiment_dir, domain)
        if os.path.isdir(domain_path):
            for example_id in os.listdir(domain_path):
                example_path = os.path.join(domain_path, example_id)
                if os.path.isdir(example_path):
                    out_path = os.path.join(example_path, "output_video.mp4")
                    process_task(example_path, out_path, fps)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Process tasks and create a video with overlaid instructions and actions."
    )
    parser.add_argument(
        "--results_dir",
        type=str,
        default="./results",
        help="Directory where the results are stored.",
    )
    parser.add_argument(
        "--action_space", type=str, default="pyautogui", help="Action space type."
    )
    parser.add_argument(
        "--obs_type", type=str, default="a11y_tree", help="Observation type."
    )
    parser.add_argument("--model_name", type=str, default="gpt-4o", help="Model name.")
    parser.add_argument("--run_id", type=str, default="0", help="Run ID.")
    parser.add_argument(
        "--fps", type=float, default=0.5, help="Frames per second for the output video."
    )

    args = parser.parse_args()

    process_tasks(
        args.results_dir,
        args.action_space,
        args.obs_type,
        args.model_name,
        args.run_id,
        args.fps,
    )
