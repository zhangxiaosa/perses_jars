import argparse
import subprocess
import threading
import time
import os
import shutil
import multiprocessing
from multiprocessing import Process, Manager
from tabulate import tabulate


class Reducer:
    def __init__(self, name, working_folder, cmd, program_to_reduce, property_test, rename_after_reduction, jobs, extra_cmd, shared_dict):
        self.name = name
        self.cmd = cmd
        self.program_to_reduce = program_to_reduce
        self.property_test = property_test
        self.rename_after_reduction = rename_after_reduction
        self.jobs = jobs
        self.start_time = None
        self.end_time = None
        self.current_size = None
        self.previous_size = None
        self.sizes = []
        self.exit_code = None
        self.log = []
        self.working_folder = os.path.join(working_folder, name)
        self.process = None
        self.extra_cmd = extra_cmd
        self.shared_dict = shared_dict

    def setup_reducer(self):
        if not os.path.exists(self.working_folder):
            os.makedirs(self.working_folder)
            print(f"Created folder: {self.working_folder}")
        shutil.copy(self.program_to_reduce, self.working_folder)
        shutil.copy(self.property_test, self.working_folder)
        os.chdir(self.working_folder)
        self.original_size = self.count(os.path.join(self.working_folder, self.program_to_reduce))

    def run_cmd(self, cmd, output_file="/dev/null", error_file="/dev/null"):
        if cmd is None:
            return None
        with open(output_file, 'w') as out, open(error_file, 'w') as err:
            self.process = subprocess.Popen(cmd, shell=True, stdout=out, stderr=err)
            self.process.wait()
        return self.process

    def run(self):
        self.start_time = time.time()
        print(f"Starting reducer: {self.name}")
        try:
            self.shared_dict[self.name] = {'status': 'running'}
            result = self.run_cmd(self.cmd,
                                  output_file=os.path.join(self.working_folder, 'stdout.log'),
                                  error_file=os.path.join(self.working_folder, 'stderr.log'))
            self.end_time = time.time()

            if result:
                self.exit_code = result.returncode
                if result.returncode != 0:
                    print(f"{self.name} command exited: {self.cmd}")
                else:
                    self.log.append(f"{self.name} ran successfully.")

            # run formatter
            self.format()

            # run renamer
            if self.rename_after_reduction:
                self.log.append(f"{self.name} starts renaming.")
                self.rename()
            
            self.shared_dict[self.name] = {'status': 'done'}
            
        except KeyboardInterrupt:
            print(f"{self.name} received KeyboardInterrupt, terminating process...")
            self.stop()
            self.end_time = time.time()
            self.exit_code = -1  # Indicate that the process was terminated by user
            self.shared_dict[self.name] = {'status': 'killed'}

    def rename(self):
        rename_cmd = f"time ~/CCECReduce/docker/scripts/run_rename.sh \
        {self.property_test} {self.program_to_reduce} {self.program_to_reduce} {self.jobs}"
        self.run_cmd(rename_cmd,
                     output_file=os.path.join(self.working_folder, 'rename_stdout.log'),
                     error_file=os.path.join(self.working_folder, 'rename_stderr.log'))
        
    def format(self):
        format_cmd = f"format -i {os.path.join(self.working_folder, self.program_to_reduce)}"
        self.run_cmd(format_cmd)

    def record_size(self, size):
        self.previous_size = self.current_size
        self.current_size = size
        self.sizes.append(size)

    def stop(self):
        if self.process:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()

    def count(self, filename):
        try:
            with open(filename, 'r') as file:
                return len(file.read())
        except FileNotFoundError:
            return None

    def check_updates(self):
        self.run_cmd(self.extra_cmd)
        size = self.count(os.path.join(self.working_folder, self.program_to_reduce))
        if size is None:
            size = 'null'
        if size != self.current_size:
            self.record_size(size)
            return True
        return False

class ReducerRunner:
    def __init__(self, args):
        self.rename_after_reduction = args.rename_after_reduction
        self.program_to_reduce = args.program_to_reduce
        self.property_test = args.property_test
        self.reducers = args.reducers.split(',') if args.reducers != 'all' else ['perses', 'creduce', 'llvm-reduce']
        self.slow = args.slow
        self.jobs = args.jobs
        self.all_reducers_done = False
        self.working_folder = os.path.join(os.getcwd(), f"reduction_results_{time.strftime('%Y%m%d_%H%M%S')}")
        self.executor = None
        self.update_thread = None
        self.shared_dict = Manager().dict()

        if not os.path.exists(self.working_folder):
            os.makedirs(self.working_folder)
            print(f"Created folder: {self.working_folder}")

        if self.slow:
            self.reducers = [reducer.replace('perses', 'perses_slow_mode').replace('creduce', 'creduce_slow_mode') for reducer in self.reducers]

        self.reducer_objects = {
            'perses': Reducer(
                name='perses', 
                working_folder=self.working_folder, 
                cmd=f'time ~/CCECReduce/docker/scripts/run_perses.sh {self.property_test} {self.program_to_reduce} {self.jobs}', 
                program_to_reduce=self.program_to_reduce, 
                property_test=self.property_test, 
                rename_after_reduction=self.rename_after_reduction, 
                jobs=self.jobs,
                extra_cmd=f"cp {os.path.join(self.working_folder, 'perses', 'perses_result', self.program_to_reduce)} {os.path.join(self.working_folder, 'perses')}",
                shared_dict=self.shared_dict
            ),
            'perses_slow_mode': Reducer(
                name='perses_slow_mode', 
                working_folder=self.working_folder, 
                cmd=f'time ~/CCECReduce/docker/scripts/run_perses_slow_mode.sh {self.property_test} {self.program_to_reduce} {self.jobs}', 
                program_to_reduce=self.program_to_reduce, 
                property_test=self.property_test, 
                rename_after_reduction=self.rename_after_reduction, 
                jobs=self.jobs,
                extra_cmd=f"cp {os.path.join(self.working_folder, 'perses_slow_mode', 'perses_result', self.program_to_reduce)} {os.path.join(self.working_folder, 'perses_slow_mode')}",
                shared_dict=self.shared_dict
                ),
            'creduce': Reducer(
                name='creduce', 
                working_folder=self.working_folder, 
                cmd=f'time ~/CCECReduce/docker/scripts/run_creduce.sh {self.property_test} {self.program_to_reduce} {self.jobs}', 
                program_to_reduce=self.program_to_reduce, 
                property_test=self.property_test, 
                rename_after_reduction=self.rename_after_reduction, 
                jobs=self.jobs,
                extra_cmd=None,
                shared_dict=self.shared_dict
            ),
            'creduce_slow_mode': Reducer(
                name='creduce_slow_mode', 
                working_folder=self.working_folder, 
                cmd=f'time ~/CCECReduce/docker/scripts/run_creduce_slow_mode.sh {self.property_test} {self.program_to_reduce} {self.jobs}', 
                program_to_reduce=self.program_to_reduce, 
                property_test=self.property_test, 
                rename_after_reduction=self.rename_after_reduction, 
                jobs=self.jobs,
                extra_cmd=None,
                shared_dict=self.shared_dict
            ),
            'llvm-reduce': Reducer(
                name='llvm-reduce', 
                working_folder=self.working_folder, 
                cmd=f'llvm-reduce --in-place --test {self.property_test} -j {self.jobs} {self.program_to_reduce}', 
                program_to_reduce=self.program_to_reduce, 
                property_test=self.property_test, 
                rename_after_reduction=self.rename_after_reduction, 
                jobs=self.jobs,
                extra_cmd=None,
                shared_dict=self.shared_dict
            ),
        }

        # Log the initial arguments
        self.log(f"Initial arguments: {args}")

    def run_cmd(self, cmd):
        if cmd is None:
            return None
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"Command failed: {cmd}\nError: {result.stderr}")
        return result.stdout

    def run_reducers(self):
        self.reducer_selected = [self.reducer_objects[reducer] for reducer in self.reducers]
        processes = []
        for reducer in self.reducer_selected:
            reducer.setup_reducer()
            p = Process(target=reducer.run)
            processes.append(p)
            p.start()
            print(f"Started process for reducer: {reducer.name}")

        return processes


    def check_updates(self):
        while not self.all_reducers_done:
            sizes_changed = False
            for reducer in self.reducer_selected:
                if reducer.check_updates():
                    sizes_changed = True
            if sizes_changed:
                timestamp = time.strftime('%Y-%m-%d %H:%M:%S')

                table_data = []
                for reducer in self.reducer_selected:
                    size_info = f"{reducer.current_size} / {reducer.original_size} ({reducer.current_size/reducer.original_size:.2%})"
                    status_info = self.shared_dict.get(reducer.name, {}).get('status')
                    table_data.append([reducer.name, size_info, status_info])

                headers = ["Reducer", "Size", "Status"]
                table = tabulate(table_data, headers, tablefmt="grid")

                self.log(f"Timestamp: {timestamp}")
                self.log(table)
                self.log("-----------------------------------")

            time.sleep(1)

        self.log("All reducers have completed. Exiting script.")


    def log(self, message):
        log_path = os.path.join(self.working_folder, 'stdout.log')
        if os.path.exists(log_path):
            mode = 'a'
        else:
            mode = 'w'

        with open(log_path, mode) as out_log:
            out_log.write(message + '\n')

        print(message)

    def start(self):
        try:
            processes = self.run_reducers()

            self.update_thread = threading.Thread(target=self.check_updates)
            self.update_thread.daemon = True
            self.update_thread.start()

            for p in processes:
                p.join()
            self.all_reducers_done = True

        except KeyboardInterrupt:
            print("Caught KeyboardInterrupt, stopping reducers...")
            self.stop_reducers()
        except Exception as e:
            print(f"An error occurred: {e}")
            self.stop_reducers()
        finally:
            self.all_reducers_done = True

        self.update_thread.join()

        timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
        size_status = " | ".join([f"{reducer.name}: {reducer.current_size:<10} ({reducer.current_size/reducer.original_size:.2%})" for reducer in self.reducer_selected])
        status = " | ".join([
            f"{reducer.name}: {self.shared_dict.get(reducer.name, {}).get('status')}"
            for reducer in self.reducer_selected
        ])
        self.log(f"Timestamp: {timestamp}\n{'reducer:':<10} {size_status}\n{'status:':<10} {status}")
        self.log("-----------------------------------")

    def stop_reducers(self):
        for reducer in self.reducer_selected:
            reducer.stop()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run multiple reducers on a program.")
    parser.add_argument('--rename-after-reduction', action='store_true', help='Whether to rename symbols after reduction.')
    parser.add_argument('--reducers', type=str, default='all', help='Comma-separated list of reducers to use (perses,creduce,llvm-reduce). Default is "all".')
    parser.add_argument('--slow', action='store_true', help='Reduce harder, may be slow.')
    parser.add_argument('--jobs', type=int, default=4, help='Number of processes or threads to use.')
    parser.add_argument('--program-to-reduce', type=str, required=True, help='The program to reduce.')
    parser.add_argument('--property-test', type=str, required=True, help='The property test to apply.')

    args = parser.parse_args()

    runner = ReducerRunner(args)
    runner.start()
