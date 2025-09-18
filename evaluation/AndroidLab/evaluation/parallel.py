from queue import Queue
import concurrent
from evaluation.auto_test import *


def task_done_callback(future, docker_instance, free_dockers):
    free_dockers.put(docker_instance)


def parallel_worker(class_, config, parallel, tasks):
    free_dockers = Queue()
    for idx in range(parallel):
        if config.docker:
            instance = Docker_Instance(config, idx)
        else:
            instance = Instance(config, idx)
        free_dockers.put(instance)

    with concurrent.futures.ThreadPoolExecutor(max_workers=parallel) as executor:
        while tasks:
            if free_dockers.empty():
                time.sleep(0.5)
                continue

            instance = free_dockers.get()
            task = tasks.pop(0)

            config_copy = copy.deepcopy(config)
            auto_class = class_(config_copy)

            future = executor.submit(auto_class.run_task, task, instance)
            future.add_done_callback(lambda fut, di=instance: task_done_callback(fut, di, free_dockers))
