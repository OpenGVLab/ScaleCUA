import os
import json
import argparse


def get_result(action_space, use_model, observation_type, result_dir):
    target_dir = os.path.join(result_dir, action_space, observation_type, use_model)
    if not os.path.exists(target_dir):
        print("New experiment, no result yet.")
        return None

    all_result = []
    domain_result = {}
    all_result_for_analysis = {}
    multi_apps_result = {}

    for domain in os.listdir(target_dir):
        domain_path = os.path.join(target_dir, domain)
        if os.path.isdir(domain_path):
            for example_id in os.listdir(domain_path):
                example_path = os.path.join(domain_path, example_id)
                if os.path.isdir(example_path):
                    if "result.txt" in os.listdir(example_path):
                        # empty all files under example_id
                        if domain not in domain_result:
                            domain_result[domain] = []
                        result = open(
                            os.path.join(example_path, "result.txt"), "r"
                        ).read()
                        try:
                            domain_result[domain].append(float(result))
                        except:
                            domain_result[domain].append(float(eval(result)))

                        if domain not in all_result_for_analysis:
                            all_result_for_analysis[domain] = {}
                        all_result_for_analysis[domain][example_id] = domain_result[
                            domain
                        ][-1]

                        try:
                            result = open(
                                os.path.join(example_path, "result.txt"), "r"
                            ).read()
                            try:
                                all_result.append(float(result))
                            except:
                                all_result.append(float(bool(result)))
                        except:
                            all_result.append(0.0)

    for domain in domain_result:
        print(
            "Domain:",
            domain,
            "Runned:",
            len(domain_result[domain]),
            "Success Rate:",
            sum(domain_result[domain]) / len(domain_result[domain]) * 100,
            "%",
        )

    print(">>>>>>>>>>>>>")
    print(
        "Office",
        "Success Rate:",
        sum(
            domain_result["libreoffice_calc"]
            + domain_result["libreoffice_impress"]
            + domain_result["libreoffice_writer"]
        )
        / len(
            domain_result["libreoffice_calc"]
            + domain_result["libreoffice_impress"]
            + domain_result["libreoffice_writer"]
        )
        * 100,
        "%",
    )
    print(
        "Daily",
        "Success Rate:",
        sum(
            domain_result["vlc"]
            + domain_result["thunderbird"]
            + domain_result["chrome"]
        )
        / len(
            domain_result["vlc"]
            + domain_result["thunderbird"]
            + domain_result["chrome"]
        )
        * 100,
        "%",
    )
    print(
        "Professional",
        "Success Rate:",
        sum(domain_result["gimp"] + domain_result["vs_code"])
        / len(domain_result["gimp"] + domain_result["vs_code"])
        * 100,
        "%",
    )

    with open(os.path.join(target_dir, "all_result.json"), "w") as f:
        f.write(str(all_result_for_analysis))

    print(
        "Runned:",
        len(all_result),
        "Current Success Rate:",
        sum(all_result) / len(all_result) * 100,
        "%",
    )
    multi_result, multi_num = 0, 0
    single_result, single_num = 0, 0
    for domain, result in domain_result.items():
        if domain == "multi_apps":
            print("Multi Apps Success Rate:", sum(result) / len(result) * 100, "%")
        else:
            single_result += sum(result)
            single_num += len(result)
    print("Single Apps Success Rate:", single_result / single_num * 100, "%")

    if not all_result:
        print("New experiment, no result yet.")
        return None
    else:

        return all_result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Show results for the benchmark")
    args = parser.parse_args()
    # environment config
    parser.add_argument("--result_folder", type=str, default=None)
    parser.add_argument("--model_name", type=str, default=None)
    result = get_result("pyautogui", args.model_name, "screenshot", args.result_folder)
