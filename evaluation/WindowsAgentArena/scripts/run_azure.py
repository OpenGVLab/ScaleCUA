# other imports
import traceback
import os
import json
import logging
from multiprocessing import Process
from pathlib import Path
from datetime import datetime
import argparse
import time

# imports from SDK V2
from datetime import datetime

from azure.ai.ml import Input, MLClient, Output, command
from azure.ai.ml.constants import AssetTypes, InputOutputModes
from azure.identity import DefaultAzureCredential
from azure.ai.ml.entities import ComputeInstance, AmlCompute, Data, ScriptReference, SetupScripts, IdentityConfiguration, ManagedIdentityConfiguration, UserIdentityConfiguration, AssignedUserConfiguration

# imports for SDK V1
from azureml.core import Workspace, Dataset, Experiment, Environment, Datastore, ScriptRunConfig
from azureml.core.runconfig import RunConfiguration, DockerConfiguration  
from azureml.core.compute import ComputeTarget
from azureml.core.environment import Environment, DockerSection
from azureml.data.dataset_consumption_config import DatasetConsumptionConfig
from azureml.data import OutputFileDatasetConfig

# Create a directory for logs if it doesn't exist
log_directory = "./azure_logs"
os.makedirs(log_directory, exist_ok=True)

# Create a log filename with the current date
log_filename = f"run_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.log"
log_filepath = os.path.join(log_directory, log_filename)

# Configure logging to output to both the console and the log file
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),  # Output to console
        logging.FileHandler(log_filepath)  # Output to log file
    ]
)

experiments_json = None

def load_args_as_dict():
    parser = argparse.ArgumentParser(description='Script to create a Windows Arena run for benchmarking on Azure ML.')
    parser.add_argument('--ci_startup_script_path', default='Users/rbonatti/compute-instance-startup.sh', help='Path to the startup script for the compute instance (default: Users/rbonatti/compute-instance-startup.sh)')  
    parser.add_argument('--agent', default='navi', help='Agent to use (default: navi)')  
    parser.add_argument('--datastore_input_path', default='storage' , help='Datastore input path (default: storage)')  
    parser.add_argument('--docker_img_name', default='windowsarena/winarena:latest', help='Docker image name (default: winarena)')  
    parser.add_argument('--exp_name', default='exp0', help='Experiment name (default: exp0)')  
    parser.add_argument('--num_workers', type=int, default=2, help='Number of Worker Instances (default: 1)')  
    parser.add_argument('--use_managed_identity', type=bool, default=False, help='Use Managed Identity (default: False)')  
    parser.add_argument('--json_name', default='evaluation_examples_windows/test_all.json', help='Name of the JSON file (default: evaluation_examples_windows/test_all.json)')  
    parser.add_argument('--model_name', default='gpt-4o-mini', help='Model name (default: gpt-4o-mini)') #gpt-4o-mini or gpt-4-vision-preview or gpt-4o or gpt-4-1106-vision-preview  
    parser.add_argument('--som_origin', default='oss', help='Origin of the SOM (default: internal)') #internal or oss or a11y or mixed  
    parser.add_argument('--a11y_backend', default='uia', help='Type of acc tree. uia more precise, win32 faster') #uia (slower) or win32 (faster)
    args, _ = parser.parse_known_args()
    return vars(args)

def launch_vm_and_job(  worker_id, 
                        exp_name, 
                        docker_config: DockerConfiguration,
                        datastore_input_path: str,
                        num_workers: int,
                        agent: str,
                        azure_config: dict,
                        docker_img_name: str,
                        ci_startup_script_path: str,
                        use_managed_identity: bool,
                        json_name: str,
                        model_name: str,
                        som_origin: str,
                        a11y_backend: str
                        ):
    subscription_id = azure_config['AZURE_SUBSCRIPTION_ID']
    resource_group = azure_config['AZURE_ML_RESOURCE_GROUP']
    workspace_name = azure_config['AZURE_ML_WORKSPACE_NAME']

    ml_client = MLClient(
        DefaultAzureCredential(), subscription_id, resource_group, workspace_name
    )
    ws = Workspace(subscription_id=subscription_id, resource_group=resource_group, workspace_name=workspace_name)

    custom_name = "docker-image-example-created" + datetime.now().strftime("%Y%m%d%H%M")
    env = Environment.from_docker_image(name=custom_name, image=docker_img_name)

    #### CREATE THE STARTUP SCRIPT
    startup_script_ref = ScriptReference(
        path=ci_startup_script_path,
        timeout_minutes=10
    )
    setup_scripts = SetupScripts(startup_script=startup_script_ref)

    #### CREATE THE DATA STORE
    datastore = Datastore.get(workspace=ws, datastore_name="workspaceblobstore")

    compute_instance_name = "w" + str(worker_id) + "Exp" + exp_name

    try:
        compute_instance = ml_client.compute.get(compute_instance_name)
        logging.info("Compute instance " + compute_instance_name + " already exists. Skipping creation")
        logging.info(f"Compute instance status: {compute_instance.state}") # Stopped, Starting, Running, Stopping
        if compute_instance.state != "Running":
            ml_client.compute.begin_start(compute_instance_name).wait()
            logging.info(f"Compute instance {compute_instance_name} has been started.")
        else:
            logging.info(f"Compute instance {compute_instance_name} is already {compute_instance.state}.")
    except:
        # start the compute instance, if it doesn't exist
        logging.info(f"Creating compute instance {compute_instance_name}...")

        if use_managed_identity:
            identity_config = ManagedIdentityConfiguration(
                client_id=azure_config['AZURE_MANAGED_IDENTITY_CLIENT_ID'],
                resource_id="subscriptions/" + azure_config['AZURE_SUBSCRIPTION_ID'] + "/resourceGroups/" + azure_config['AZURE_ML_RESOURCE_GROUP'] + "/providers/Microsoft.ManagedIdentity/userAssignedIdentities/" + azure_config['AZURE_ML_USER_ASSIGNED_IDENTITY'],
                object_id=azure_config['AZURE_MANAGED_IDENTITY_OBJECT_ID'],
                principal_id=azure_config['AZURE_MANAGED_IDENTITY_PRINCIPAL_ID'],
            )

            identity = IdentityConfiguration(
                type="UserAssigned",
                user_assigned_identities=[identity_config]
            )

            compute_instance = ComputeInstance(name=compute_instance_name, 
                                    size="Standard_D8_v3", 
                                    setup_scripts=setup_scripts,
                                    idle_time_before_shutdown_minutes=600,
                                    ssh_public_access_enabled=True,
                                    identity=identity
                                    )
        else:
            compute_instance = ComputeInstance(name=compute_instance_name, 
                                    size="Standard_D8_v3", 
                                    setup_scripts=setup_scripts,
                                    idle_time_before_shutdown_minutes=600,
                                    ssh_public_access_enabled=True
                                    )
        ml_client.begin_create_or_update(compute_instance).result()
        logging.info(f"Compute instance {compute_instance_name} created")

    # start the job
    logging.info(f"Starting job on compute instance {compute_instance_name}...")
    compute_target = ComputeTarget(workspace=ws, name=compute_instance_name)
    run_config = RunConfiguration()  
    run_config.target = compute_target  
    run_config.environment = env  
    run_config.docker = docker_config  
    # Check for required environment variables
    if 'OPENAI_API_KEY' in azure_config:
        run_config.environment_variables = {
            "OPENAI_API_KEY": azure_config['OPENAI_API_KEY']
        }
    elif 'AZURE_API_KEY' in azure_config and 'AZURE_ENDPOINT' in azure_config:
        run_config.environment_variables = {
            "AZURE_API_KEY": azure_config['AZURE_API_KEY'],
            "AZURE_ENDPOINT": azure_config['AZURE_ENDPOINT']
        }
    else:
        raise KeyError("Either 'OPENAI_API_KEY' must be available or both 'AZURE_API_KEY' and 'AZURE_ENDPOINT' must be available.")

    input_dataset = Dataset.File.from_files(path=(datastore, datastore_input_path))
    input = input_dataset.as_named_input('input').as_mount('/tmp/input')
    output = OutputFileDatasetConfig(destination=(datastore, '/agent_outputs/'))

    src = ScriptRunConfig(source_directory="./azure_files",
                        script='run_entry.py',
                        arguments=[input, output, exp_name, num_workers, worker_id, agent, json_name, model_name, som_origin, a11y_backend],
                        run_config=run_config)

    experiment = Experiment(workspace=ws, name=exp_name)  
    run = experiment.submit(config=src)  
    
    # get a URL for the status of the job  
    logging.info(f'Job submitted: {run.get_portal_url()}\nJob started on compute instance {compute_instance_name}\nJob ID: {run.id}')

    # Monitor the job  
    logging.info("Waiting for job completion...")
    run.wait_for_completion(show_output=False)  
  
    # Delete the VM once the job is done  
    logging.info(f"Deleting compute instance {compute_instance_name}...")  
    delete_poller = ml_client.compute.begin_delete(compute_instance_name)
    
    # Wait for resource cleanup  
    try:
        logging.info("Waiting for instance deletion...")
        delete_poller.result()
        time.sleep(60)
    except Exception as err:
        logging.error("Error while waiting for instance deletion...")
        logging.exception(err)
    

def launch_experiment(config):
    
    #### CREATE THE CREDENTIALS FROM THE CONFIG FILE
    script_dir = Path(__file__).parent
    config_path = script_dir / '..' / 'config.json'
    with config_path.resolve().open('r') as f:
        azure_config = json.load(f)

    subscription_id = azure_config['AZURE_SUBSCRIPTION_ID']
    resource_group = azure_config['AZURE_ML_RESOURCE_GROUP']
    workspace_name = azure_config['AZURE_ML_WORKSPACE_NAME']

    ml_client = MLClient(
        DefaultAzureCredential(), subscription_id, resource_group, workspace_name
    )
    ws = Workspace(subscription_id=subscription_id, resource_group=resource_group, workspace_name=workspace_name)


    #### CREATE THE ENVIRONMENT
    # env = Environment(
    #     image="windowsarena/winarena:latest",
    #     name="winarena",
    #     description="Windows Arena Environment.",
    # )
    # ml_client.environments.create_or_update(env)
    #### alternative: if we want a brand new environment:

    #### CREATE THE DOCKER CONFIGURATION
    docker_config = DockerConfiguration(use_docker=True, shared_volumes=True, arguments=["--cap-add", 'NET_ADMIN'], shm_size='16g')

    #### CREATE THE EXPERIMENTS
    experiments = []
    for i in range(config['num_workers']):
        p = Process(target=launch_vm_and_job, args=(i, config['exp_name'], docker_config, config['datastore_input_path'], 
            config['num_workers'], config['agent'], azure_config, config['docker_img_name'], config['ci_startup_script_path'],
            config['use_managed_identity'], config['json_name'], config['model_name'], config['som_origin'], config['a11y_backend']))
        experiments.append(p)
        p.start()

    for experiment in experiments:
        experiment.join()

    logging.info("All experiments have been completed.")

def launch_batch(experiments):
    for exp_name, config in experiments.items():
        if config.get('_done', False) or '_stop_time' in config:
            logging.info(f"Skipping experiment: {exp_name} as it has already been completed.")
            continue
        
        if '_start_time' in config and '_stop_time' not in config:
            user_input = input(f"Experiment '{exp_name}' was already started. Do you want to continue? (yes/no/skip): ").strip().lower()
            if user_input == 'skip':
                logging.info(f"Skipping experiment: {exp_name}.")
                continue
            elif user_input != 'yes':
                logging.info(f"Skipping experiment: {exp_name} based on user input.")
                continue

        logging.info(f"Launching experiment: {exp_name}")
        # save start timestamp
        config['_start_time'] = config.get('_start_time', time.strftime('%Y-%m-%d %H:%M:%S'))
        save_exps(experiments)
        # launch exp
        launch_experiment(config)
        # save end timestamp
        config['_stop_time'] = time.strftime('%Y-%m-%d %H:%M:%S')
        config['_done'] = True
        save_exps(experiments)

def save_exps(experiments):
    if experiments_json:
        with open(experiments_json, 'w') as f:
            json.dump(experiments, f, indent=2)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Run Azure ML experiments')
    parser.add_argument('--experiments_json', help='Path to JSON file containing multiple experiments')
    parser.add_argument('--update_json', action='store_true', help='Update the experiments JSON with provided arguments')
    args, _ = parser.parse_known_args()
    
    if args.experiments_json:
        experiments_json = args.experiments_json
    
    if args.experiments_json and args.update_json:        
        try:
            # Load existing experiments JSON
            if os.path.exists(args.experiments_json):
                with open(args.experiments_json, 'r') as f:
                    experiments = json.load(f)
                logging.info(f"====== OLD EXPERIMENTS.JSON ======")
                logging.info(json.dumps(experiments, indent=2))
                logging.info(f"==================================")
            else:
                experiments = {}
            
            # Parse and save experiment arguments
            exp_config = load_args_as_dict()
            exp_name = exp_config["exp_name"]
            
            # Preserve existing keys starting with '_' in the experiment config
            existing_config = {k: v for k, v in experiments.get(exp_name, {}).items() if k.startswith('_')}
            exp_config = {**existing_config, **exp_config}  # Merge with new config

            experiments[exp_name] = exp_config

            # Save updated experiments JSON
            save_exps(experiments)
            
            # Save updated experiments JSON
            save_exps(experiments)
            logging.info(f"====== NEW EXPERIMENTS.JSON ======")
            logging.info(json.dumps(experiments, indent=2))
            logging.info(f"==================================")
            
            logging.info(f"Successfully updated {args.experiments_json}")

        except Exception as e:
            logging.error(f"Error updating experiments JSON: {str(e)}")
    elif args.experiments_json:
        try:
            with open(args.experiments_json, 'r') as f:
                experiments = json.load(f)
            launch_batch(experiments)
        except Exception as e:
            logging.error(f"Error loading experiments from JSON: {str(e)}")
            # Print the stack trace
            traceback.print_exc()
    else:
        try:
            config = load_args_as_dict()
            launch_experiment(config)
        except Exception as e:
            logging.error(f"Error launching single experiment: {str(e)}")
            # Print the stack trace
            traceback.print_exc()