from time import time

import yaml
from config.config import Config
from detect_engine.detect_engine import DriftDectionEngine
from llm.llm import LLM
from tools.discover_resource_files import *
import time
import json
from logger.logger import LoggerSentinel
from tools.github import git_stash


#loading the config
config_path = "../config.yaml"
schema_path = "../required_schema.yaml"
dotenv_path = "../.env"

config = Config(config_path, schema_path, dotenv_path)
config.load()
watch = config.environments
drift_interval = config.drift_detection.get('interval_seconds')


#Drift detction engine
paths = watch.get('environments')
terraform_variant = config.terraform_variant
print("The variant of terraform being used is:", terraform_variant)
drift_detection_engine = DriftDectionEngine(paths=paths, terraform_variant=terraform_variant)

#llm config
model = config.llm.get('model')
ollama_endpoint = config.llm.get('endpoint')
api_key = config.llm_api_key

print(f"Using LLM model: {model}")
print(f"Using LLM endpoint: {ollama_endpoint}")


template_paths = {
    "iac_drift_expert": "llm/iac_drift_template.yaml",
    "iac_drift_patch_expert": "llm/iac_drift_patch_template.yaml",
    "iac_drift_pr_expert": "llm/iac_drift_pr_template.yaml",
}

templates = {}
for key, path in template_paths.items():
    with open(path, 'r') as file:
        prompt_template = yaml.safe_load(file)
        templates[key] = prompt_template

llm = LLM(ollama_endpoint, api_key, prompt_templates=templates)

logger = LoggerSentinel(config.log_path, config.failure_log_path)


while True:
    print("Checking for IaC drift...")
    # perform drift detection logic here
    stage = "scan_terraform_plan"
    environment = "unknown"
    path = "unknown"

    try:
        scans = drift_detection_engine.run_all_paths_terraform_plan()
        #print(f"Drift detection scans: {scans}")
        for environment in scans:
            for path in scans[environment]:
                print(f"Drift scan results for environment '{environment}' at path '{path}':")
                print("\n\n")
                plan_output_json = scans[environment][path]
                print("Plan output json scanned")
                drifts = drift_detection_engine.get_drifted_resources(plan_output_json)
                print(f"Drifted resources for environment '{environment}' at path '{path}':")
                print(drifts)

                #skipping drifts that are already patched
                print("Filtering out drifts that are already patched...")
                drifts = [drift for drift in drifts if not logger.is_patch_exist(path, model,drift)]
                print(f"Drifts after filtering already patched ones for environment '{environment}' at path '{path}':")
                print(drifts)

                if not drifts or len(drifts) == 0:
                    print(f"No new drifts detected for environment '{environment}' at path '{path}'.")
                    continue

                print("Generating recommendations...")
                recommendations = llm.initial_recommendation(
                    model=model,
                    drift_scan = json.dumps(drifts),
                    watch=watch
                )
                print(f"Recommendations for environment '{environment}' at path '{path}':")
                print(recommendations)


                recommendations_list = yaml.safe_load(recommendations)
                for drift, recommendation in zip(drifts, recommendations_list):
                    if recommendation.get('fix_type') == 'code_patch':
                        #get the resources map
                        stage="discovering_terraform_files"
                        resources_map = discover_terraform_files(path)
                        #print(f"Resources map for path {path}: {resources_map}")
                        stage="normalizing_terraform_state"
                        resource_map_simplified = normalize_terraform_states(resources_map['resource_map'])
                        #print(f"Normalized resource map for path {path}: {resource_map_simplified}")

                        stage="parsing_terraform_address"
                        components = parse_terraform_address(recommendation.get('resource_name'))
                        print(f"Parsed components for resource {recommendation.get('resource_name')}: {components}")

                        stage="building_llm_patch_context"
                        patch_context = build_llm_patch_context(recommendation, drift,resource_map_simplified)
                        print(f"LLM Patch Context for resource {recommendation.get('resource_name')}: {patch_context}")
                        #exit(0)

                        print(f"Generating code update patch for {environment} at path {path}...")
                        stage="generating_code_patch"
                        patch = llm.fix_drift_patch(model=model, llm_patch_context=patch_context)
                        print(f"Generated Patch File(s): {patch}")

                        #refresh the terraform after applying the patch
                        print(f"Applying generated patch to files...")
                        stage="refreshing_terraform_state"
                        refresh_resource = components.get('resource_full_name')
                        refresh_result = drift_detection_engine.refresh_terraform_state(path, refresh_resource)
                        

                        #did we get a error?
                        if refresh_result.get("status")=="error":
                            logger.log_drift_event(
                                environment=environment,
                                path=path,
                                model=model,
                                resource=recommendation.get('resource_name'),
                                attribute=patch_context["change_area"]["attribute"],
                                patch_context=patch_context,
                                correct_method=patch_context["change_area"]["method"],
                                opensentinel_method="terraform_refresh",
                                refresh_clean=False
                            )
                            raise RuntimeError(f"Error occurred during terraform refresh: {refresh_result.get('stderr')}")
                        #log the patch as successful
                        logger.log_drift_event(
                            environment=environment,
                            path=path,
                            model=model,
                            resource=recommendation.get('resource_name'),
                            attribute=patch_context["change_area"]["attribute"],
                            patch_context=patch_context,
                            correct_method=patch_context["change_area"]["method"],
                            opensentinel_method="terraform_refresh",
                            refresh_clean= True
                        )
                        #print(f"Patch is {patch}")
                        patch_json = json.loads(patch)
                        modified_files = patch_json.get('modified_files', [])
                        if modified_files and len(modified_files) > 0:
                            print("Generating Github PR for the applied patch...")
                            stage="generating_github_pr"
                            pr_response = llm.make_drift_pr(
                                model = model,
                                recommendation = recommendation,
                                directory = path,
                                modified_files = modified_files,
                                token = config.github_token
                            )

                            #storing the already patched drift in the logger to prevent future duplicate patching
                            log_drift = {
                                "address": recommendation.get('resource_name'),
                                "attribute_path": patch_context["change_area"]["attribute"],
                                "before": patch_context["drifted_values"]["before"],
                                "after": patch_context["drifted_values"]["after"]
                            }

                            logger.save_patch(environment, path, model,log_drift)
                            #logger.log_patch(log_drift)

                            print(f"PR Response: {pr_response}")

                #we  already patched the changes in this environment so we can stash any local changes as we do not want to keep any local copies
                #print(f"Stashing any local changes in environment '{environment}' at path '{path}'...")
                #git_stash(path)
    except Exception as e:
        logger.log_orchestration_failure(
            environment=environment,
            path=path,
            model=model,
            stage=stage,
            error=e
        )
        print(f"Error occurred during drift detection orchestration at stage '{stage}': {e}")
    print(f"Waiting for {drift_interval} seconds before next drift check...")

    time.sleep(drift_interval)



