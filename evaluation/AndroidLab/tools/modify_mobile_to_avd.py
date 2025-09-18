import argparse
import os


def update_device_ini(avd_dir, device_name):
    device_ini_path = os.path.join(avd_dir, f'{device_name}.ini')

    with open(device_ini_path, 'r') as file:
        lines = file.readlines()

    with open(device_ini_path, 'w') as file:
        for line in lines:
            if '[ANDROID_AVD_HOME]' in line:
                line = line.replace('[ANDROID_AVD_HOME]', avd_dir)
            file.write(line)


def update_config_files(avd_dir, device_name, sdk_dir):
    avd_abs_path = os.path.join(avd_dir, f'{device_name}.avd')
    config_files = ['config.ini', 'hardware-qemu.ini']

    for config_file in config_files:
        config_path = os.path.join(avd_abs_path, config_file)

        with open(config_path, 'r') as file:
            lines = file.readlines()

        with open(config_path, 'w') as file:
            for line in lines:
                if '[ANDROID_AVD_HOME]' in line:
                    line = line.replace('[ANDROID_AVD_HOME]', avd_dir)
                if '[ANDROID_SDK_HOME]' in line:
                    line = line.replace('[ANDROID_SDK_HOME]', sdk_dir)
                file.write(line)


def main(avd_dir, sdk_dir, device_name):
    update_device_ini(avd_dir, device_name)
    update_config_files(avd_dir, device_name, sdk_dir)
    print(f'Successfully updated {device_name} AVD files.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Update AVD configuration files.")
    parser.add_argument('--avd_dir', type=str, help='AVD Storage Directory')
    parser.add_argument('--sdk_dir', type=str, help='Android SDK Directory')
    parser.add_argument('--device_name', type=str, help='Device Name')

    args = parser.parse_args()

    main(args.avd_dir, args.sdk_dir, args.device_name)
