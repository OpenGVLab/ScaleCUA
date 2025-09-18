import argparse
import os
import shutil


def update_device_ini(avd_dir, device_name, save_dir):
    device_ini_path = os.path.join(avd_dir, f'{device_name}.ini')
    save_ini_path = os.path.join(save_dir, f'{device_name}.ini')

    with open(device_ini_path, 'r') as file:
        lines = file.readlines()

    with open(save_ini_path, 'w') as file:
        for line in lines:
            if "path=" in line:
                line = f"path=/root/.android/avd/{device_name}.avd" + "\n"
            if "path.rel=" in line:
                line = f"path.rel=avd/{device_name}.avd" + "\n"
            file.write(line)


def update_config_files(avd_dir, device_name, save_dir):
    avd_abs_path = os.path.join(avd_dir, f'{device_name}.avd')
    save_avd_path = os.path.join(save_dir, f'{device_name}.avd')
    shutil.copytree(avd_abs_path, save_avd_path)

    config_files = ['config.ini']

    for config_file in config_files:
        config_path = os.path.join(avd_abs_path, config_file)
        save_config_path = os.path.join(save_dir, f'{device_name}.avd', config_file)

        with open(config_path, 'r') as file:
            lines = file.readlines()

        with open(save_config_path, 'w') as file:
            for line in lines:
                if "image.sysdir.1" in line:
                    line = "image.sysdir.1 = system-images;android-33;google_apis_playstore;x86_64" + "\n"
                if "skin.path" in line:
                    line = "skin.path = /root/.android/skins/pixel_7_pro" + "\n"
                file.write(line)


def main(avd_dir, device_name, save_dir):
    if not os.path.exists(save_dir):
        os.makedirs(save_dir)
    update_device_ini(avd_dir, device_name, save_dir)
    update_config_files(avd_dir, device_name, save_dir)

    print(f'Successfully updated {device_name} AVD files.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Update AVD configuration files.")
    parser.add_argument('--avd_dir', type=str, help='AVD Storage Directory')
    parser.add_argument('--device_name', type=str, help='Device Name')
    parser.add_argument('--save_dir', type=str, help='Directory to save modified AVD files')

    args = parser.parse_args()

    main(args.avd_dir, args.device_name, args.save_dir)
