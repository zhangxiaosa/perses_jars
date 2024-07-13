import os
import time
import subprocess
import shutil
from datetime import datetime
import argparse

def read_file(file_path):
    with open(file_path, 'r') as file:
        return file.read()

def write_log(log_message, log_file_path):
    with open(log_file_path, 'a') as log_file:
        log_file.write(log_message + '\n')
    print(log_message)

def file_changed(new_file_path, old_content):
    new_content = read_file(new_file_path)
    return new_content != old_content, new_content

def generate_patch(old_file_a_path, new_file_a_path, patch_file_path):
    subprocess.run(f'diff {old_file_a_path} {new_file_a_path} > {patch_file_path}', shell=True)

def apply_patch(old_file_b_path, patch_file_path, new_file_b_path):
    shutil.copy(old_file_b_path, new_file_b_path)
    result = subprocess.run(['patch', '-F', '10', new_file_b_path, '-i', patch_file_path], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return result.returncode == 0

def run_script(script_path, temp_dir_path):
    result = subprocess.run(['sh', script_path], cwd=temp_dir_path, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return result.returncode == 0

def main(origin_file_a_path, origin_file_b_path, origin_script_r_path):
    server_timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    server_dir_path = os.path.abspath(f'server_{server_timestamp}')
    os.makedirs(server_dir_path, exist_ok=True)
    log_file_path = os.path.join(server_dir_path, 'log.txt')

    origin_file_a_path = os.path.abspath(origin_file_a_path)
    origin_file_b_path = os.path.abspath(origin_file_b_path)
    origin_script_r_path = os.path.abspath(origin_script_r_path)

    old_a_content = read_file(origin_file_a_path)
    while True:
        time.sleep(5)
        changed, new_a_content = file_changed(origin_file_a_path, old_a_content)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        if changed:
            write_log(f"{timestamp}: File {origin_file_a_path} has changed, generating patch.", log_file_path)
            
            patch_dir_path = os.path.join(server_dir_path, timestamp)
            os.makedirs(patch_dir_path, exist_ok=True)

            old_file_a_path = os.path.join(patch_dir_path, 'old_a.txt')
            new_file_a_path = os.path.join(patch_dir_path, 'new_a.txt')
            old_file_b_path = os.path.join(patch_dir_path, 'old_b.txt')
            new_file_b_path = os.path.join(patch_dir_path, 'new_b.txt')
            new_file_b_realname_path = os.path.join(patch_dir_path, os.path.basename(origin_file_b_path))
            
            with open(new_file_a_path, 'w') as f:
                f.write(new_a_content)
            
            shutil.copy(origin_file_a_path, old_file_a_path)
            shutil.copy(origin_file_b_path, old_file_b_path)
            
            patch_file_path = os.path.join(patch_dir_path, 'patch.diff')
            generate_patch(old_file_a_path, new_file_a_path, patch_file_path)
            write_log(f"{timestamp}: Generated patch:\n{read_file(patch_file_path)}", log_file_path)

            apply_success = apply_patch(old_file_b_path, patch_file_path, new_file_b_path)
            
            if apply_success:
                write_log(f"{timestamp}: Patch applied successfully.", log_file_path)
                shutil.copy(origin_script_r_path, os.path.join(patch_dir_path, os.path.basename(origin_script_r_path)))
                shutil.copy(new_file_b_path, new_file_b_realname_path)

                if run_script(os.path.join(patch_dir_path, os.path.basename(origin_script_r_path)), patch_dir_path):
                    write_log(f"{timestamp}: Script ran successfully, updating file {origin_file_b_path}.", log_file_path)
                    shutil.copy(new_file_b_realname_path, origin_file_b_path)
                else:
                    write_log(f"{timestamp}: Script failed, not updating file {origin_file_b_path}.", log_file_path)
            else:
                write_log(f"{timestamp}: Patch failed to apply.", log_file_path)

            old_a_content = new_a_content
        else:
            write_log(f"{timestamp}: No changes detected in file {origin_file_a_path}.", log_file_path)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Monitor file changes and apply patches.')
    parser.add_argument('file_a_path', type=str, help='Path to file a')
    parser.add_argument('file_b_path', type=str, help='Path to file b')
    parser.add_argument('script_r_path', type=str, help='Path to script r.sh')

    args = parser.parse_args()
    main(args.file_a_path, args.file_b_path, args.script_r_path)
