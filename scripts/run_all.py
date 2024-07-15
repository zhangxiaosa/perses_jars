import argparse
import subprocess
import threading
import time
import os
import shutil
import multiprocessing
from multiprocessing import Process

class Reducer:
    def __init__(self, name, working_folder, cmd, program_to_reduce, property_test, rename_after_reduction, extra_cmd):
        self.name = name
        self.cmd = cmd
        self.program_to_reduce = program_to_reduce
        self.property_test = property_test
        self.rename_after_reduction = rename_after_reduction
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

    def setup_reducer(self):
        if not os.path.exists(self.working_folder):
            os.makedirs(self.working_folder)
            print(f"Created folder: {self.working_folder}")
        shutil.copy(self.program_to_reduce, self.working_folder)
        shutil.copy(self.property_test, self.working_folder)
        os.chdir(self.working_folder)

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
        result = self.run_cmd(self.cmd,
                              output_file=os.path.join(self.working_folder, 'stdout.log'),
                              error_file=os.path.join(self.working_folder, 'stderr.log'))
        self.end_time = time.time()
        if result:
            self.exit_code = result.returncode
            if result.returncode != 0:
                print(f"{self.name} command failed: {self.cmd}")
            else:
                self.log.append(f"{self.name} ran successfully.")
        if self.rename_after_reduction:
            self.rename()

    def rename(self):
        rename_cmd = f"creduce --no-default-passes \
            --add-pass pass_clex rename-toks 1 \
            --add-pass pass_clang rename-fun 1 \
            --add-pass pass_clang rename-param 1 \
            --add-pass pass_clang rename-var 1 \
            --add-pass pass_clang rename-class 1 \
            --add-pass pass_clang rename-cxx-method 1 {self.property_test} {self.program_to_reduce}"
        self.run_cmd(rename_cmd,
                     output_file=os.path.join(self.working_folder, 'rename_stdout.log'),
                     error_file=os.path.join(self.working_folder, 'rename_stderr.log'))

    def record_size(self, size):
        self.previous_size = self.current_size
        self.current_size = size
        self.sizes.append(size)

    def stop(self):
        if self.process:
            self.process.terminate()
            self.process.wait()

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
                extra_cmd=f"cp {os.path.join(self.working_folder, "perses_result", self.program_to_reduce)} {os.path.join(self.working_folder, "perses_result")}"
            ),
            'perses_slow_mode': Reducer(
                name='perses_slow_mode', 
                working_folder=self.working_folder, 
                cmd=f'time ~/CCECReduce/docker/scripts/run_perses_slow_mode.sh {self.property_test} {self.program_to_reduce} {self.jobs}', 
                program_to_reduce=self.program_to_reduce, 
                property_test=self.property_test, 
                rename_after_reduction=self.rename_after_reduction, 
                extra_cmd=f"cp {os.path.join(self.working_folder, "perses_result", self.program_to_reduce)} {os.path.join(self.working_folder, "perses_result")}"
                ),
            'creduce': Reducer(
                name='creduce', 
                working_folder=self.working_folder, 
                cmd=f'time ~/CCECReduce/docker/scripts/run_creduce.sh {self.property_test} {self.program_to_reduce} {self.jobs}', 
                program_to_reduce=self.program_to_reduce, 
                property_test=self.property_test, 
                rename_after_reduction=self.rename_after_reduction, 
                extra_cmd=None
            ),
            'creduce_slow_mode': Reducer(
                name='creduce_slow_mode', 
                working_folder=self.working_folder, 
                cmd=f'time ~/CCECReduce/docker/scripts/run_creduce_slow_mode.sh {self.property_test} {self.program_to_reduce} {self.jobs}', 
                program_to_reduce=self.program_to_reduce, 
                property_test=self.property_test, 
                rename_after_reduction=self.rename_after_reduction, 
                extra_cmd=None
            ),
            'llvm-reduce': Reducer(
                name='llvm-reduce', 
                working_folder=self.working_folder, 
                cmd=f'llvm-reduce --in-place --test {self.property_test} -j {self.jobs} {self.program_to_reduce}', 
                program_to_reduce=self.program_to_reduce, 
                property_test=self.property_test, 
                rename_after_reduction=self.rename_after_reduction, 
                extra_cmd=None
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
                size_status = "\t\t".join([f"{reducer.name}: {reducer.current_size}" for reducer in self.reducer_selected])
                status = "\t\t".join([
                    f"{reducer.name}: error" if reducer.end_time is not None and reducer.exit_code != 0 else
                    f"{reducer.name}: done" if reducer.end_time is not None else
                    f"{reducer.name}: running"
                    for reducer in self.reducer_selected
                ])
                self.log(f"Timestamp: {timestamp}\n{size_status}\n{status}")
                self.log("-----------------------------------")

            time.sleep(1)
        
        self.log("All reducers have completed. Exiting script.")


    def log(self, message):
        log_path = os.path.join(self.working_folder, 'stdout.log')
        if (os.path.exists(log_path)):
            mode = 'a'
        else:
            mode = 'w'

        with open(os.path.join(self.working_folder, 'stdout.log'), mode) as out_log:
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
