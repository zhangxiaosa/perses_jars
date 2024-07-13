import os
import time
import subprocess
import shutil
import tempfile
from datetime import datetime
import argparse

def read_file(file_path):
    with open(file_path, 'r') as file:
        return file.read()

def write_log(log_message):
    with open('./server/log.txt', 'a') as log_file:
        log_file.write(log_message + '\n')
    print(log_message)

def file_changed(file_path, last_content):
    current_content = read_file(file_path)
    return current_content != last_content, current_content

def generate_patch(file_a, temp_file):
    patch_file = tempfile.NamedTemporaryFile(delete=False)
    patch_file.close()
    subprocess.run(['diff', '-u', file_a, temp_file, '-o', patch_file.name])
    return patch_file.name

def apply_patch(file_b, patch_file):
    with tempfile.NamedTemporaryFile(delete=False) as temp_file_b:
        temp_file_b.close()
        shutil.copy(file_b, temp_file_b.name)
        result = subprocess.run(['patch', '-F', '10', temp_file_b.name, '-i', patch_file], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return result.returncode == 0, temp_file_b.name

def run_script(script_file, temp_dir):
    result = subprocess.run(['sh', script_file], cwd=temp_dir, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return result.returncode == 0

def save_files(timestamp, last_a_content, current_a_content, patch_file, old_b, new_b):
    dir_path = f'./server/{timestamp}'
    os.makedirs(dir_path, exist_ok=True)
    
    with open(f'{dir_path}/last_a.txt', 'w') as f:
        f.write(last_a_content)
    
    with open(f'{dir_path}/current_a.txt', 'w') as f:
        f.write(current_a_content)
    
    shutil.copy(patch_file, f'{dir_path}/patch.diff')
    shutil.copy(old_b, f'{dir_path}/old_b.txt')
    shutil.copy(new_b, f'{dir_path}/new_b.txt')

def main(file_a, file_b, script_r):
    last_content = read_file(file_a)
    while True:
        time.sleep(5)
        changed, new_content = file_changed(file_a, last_content)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        if changed:
            write_log(f"{timestamp}: File {file_a} has changed, generating patch.")
            
            with tempfile.NamedTemporaryFile(delete=False) as temp_file_a:
                temp_file_a.write(new_content.encode())
                temp_file_a.close()

            patch_file = generate_patch(file_a, temp_file_a.name)
            write_log(f"{timestamp}: Generated patch:\n{read_file(patch_file)}")

            apply_success, temp_file_b_path = apply_patch(file_b, patch_file)
            
            if apply_success:
                write_log(f"{timestamp}: Patch applied successfully.")
                with tempfile.TemporaryDirectory() as temp_dir:
                    shutil.copy(temp_file_b_path, os.path.join(temp_dir, os.path.basename(file_b)))
                    shutil.copy(script_r, os.path.join(temp_dir, os.path.basename(script_r)))

                    if run_script(os.path.join(temp_dir, os.path.basename(script_r)), temp_dir):
                        write_log(f"{timestamp}: Script ran successfully, updating file {file_b}.")
                        save_files(timestamp, last_content, new_content, patch_file, file_b, temp_file_b_path)
                        shutil.copy(temp_file_b_path, file_b)
                    else:
                        write_log(f"{timestamp}: Script failed, not updating file {file_b}.")
            else:
                write_log(f"{timestamp}: Patch failed to apply.")
                save_files(timestamp, last_content, new_content, patch_file, file_b, temp_file_b_path)

            last_content = new_content
        else:
            write_log(f"{timestamp}: No changes detected in file {file_a}.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Monitor file changes and apply patches.')
    parser.add_argument('file_a', type=str, help='Path to file a')
    parser.add_argument('file_b', type=str, help='Path to file b')
    parser.add_argument('script_r', type=str, help='Path to script r.sh')

    args = parser.parse_args()
    main(args.file_a, args.file_b, args.script_r)
