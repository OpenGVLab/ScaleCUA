import os
import json


def get_directory_structure(base_dir, filter_out_categories=None):
    directory_structure = {}
    total_files_count = 0

    for subdir, _, files in os.walk(base_dir):
        if subdir == base_dir:
            continue  # Skip the base directory itself

        if filter_out_categories:
            if any(category in subdir for category in filter_out_categories):
                print(f"Skipping directory: {subdir}")
                continue

        subdir_name = os.path.basename(subdir)
        file_names = [os.path.splitext(file)[0] for file in files]
        directory_structure[subdir_name] = file_names
        total_files_count += len(file_names)

        # Print the count of files per subdirectory
        print(f"Directory: {subdir_name}, File count: {len(file_names)}")

    return directory_structure, total_files_count


def main(base_dir, output_file, filter_out_categories=None):
    directory_structure, total_files_count = get_directory_structure(
        base_dir, filter_out_categories
    )

    with open(output_file, "w") as f:
        json.dump(directory_structure, f, indent=4)

    # Print the total number of files
    print(f"Total file count: {total_files_count}")


if __name__ == "__main__":
    base_dir = "examples"

    output_file = "test_all.json"
    filter_out_categories = None

    main(base_dir, output_file, filter_out_categories)
