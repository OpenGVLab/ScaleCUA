import os
import argparse
import json


def get_result(target_dir):
    if not os.path.exists(target_dir):
        print("New experiment, no result yet.")
        return None

    all_result = []
    domain_result = {}
    all_result_for_analysis = {}
    missing_domains = {}

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
                            domain_result[domain].append(float(bool(result)))

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
                    else:
                        print("No result.txt in", example_path)
                        if domain not in missing_domains:
                            missing_domains[domain] = []
                        missing_domains[domain].append(example_id)

    for domain in domain_result:
        print(
            "Domain:",
            domain,
            "Executed tasks:",
            len(domain_result[domain]),
            "Success Rate:",
            sum(domain_result[domain]) / len(domain_result[domain]) * 100,
            "%",
        )

    print(">>>>>>>>>>>>>")
    office_success_rate = (
        sum(
            domain_result.get("libreoffice_calc", [])
            + domain_result.get("libreoffice_impress", [])
            + domain_result.get("libreoffice_writer", [])
        )
        / len(
            domain_result.get("libreoffice_calc", [])
            + domain_result.get("libreoffice_impress", [])
            + domain_result.get("libreoffice_writer", [])
        )
        * 100
    )
    if office_success_rate:
        print("Office", "Success Rate:", office_success_rate, "%")
    print(
        "Daily",
        "Success Rate:",
        sum(
            domain_result.get("vlc", [])
            + domain_result.get("thunderbird", [])
            + domain_result.get("chrome", [])
        )
        / len(
            domain_result.get("vlc", [])
            + domain_result.get("thunderbird", [])
            + domain_result.get("chrome", [])
        )
        * 100,
        "%",
    )
    professional_results = domain_result.get("gimp", []) + domain_result.get(
        "vs_code", []
    )
    if professional_results:
        print(
            "Professional",
            "Success Rate:",
            sum(professional_results) / len(professional_results) * 100,
            "%",
        )
    else:
        print("Professional", "Success Rate: No data available")

    with open(os.path.join(target_dir, "all_result.json"), "w") as f:
        json.dump(all_result_for_analysis, f, indent=4)
    with open(os.path.join(target_dir, "missing.json"), "w") as f:
        json.dump(missing_domains, f, indent=4)

    if not all_result:
        print("New experiment, no result yet.")
        return None
    else:
        print(
            "Tasks executed:",
            len(all_result),
            "Current Success Rate:",
            sum(all_result) / len(all_result) * 100,
            "%",
        )
        return all_result


if __name__ == "__main__":
    # 1. Initialize the argument parser.
    parser = argparse.ArgumentParser(
        description="Process results from a specified target directory."
    )

    # 2. Add a positional argument for the target directory.
    #    By not using a '--' prefix, argparse treats this as a required positional argument.
    parser.add_argument(
        "target_dir",
        type=str,
        help="The full path to the target directory to be processed.",
    )

    # 3. Parse the arguments from the command line.
    args = parser.parse_args()

    # 4. Call your function with the path provided by the user.
    #    The value is accessed via args.target_dir.
    get_result(args.target_dir)
