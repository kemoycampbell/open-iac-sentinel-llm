from time import time

import yaml
from config.config import Config
from detect_engine.detect_engine import DriftDectionEngine
from llm.llm import LLM
import time
import json


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
drift_detection_engine = DriftDectionEngine(paths=paths, terraform_variant="terraform")

#llm config
model = config.llm.get('model')
ollama_endpoint = config.llm.get('endpoint')
api_key = config.llm_api_key

print(f"Using LLM model: {model}")
print(f"Using LLM endpoint: {ollama_endpoint}")


template_paths = {
    "iac_drift_expert": "llm/iac_drift_template.yaml",
    "iac_drift_expert_second_pass": "llm/iac_drift_template_second_pass.yaml",
    "iac_drift_patch_expert": "llm/iac_drift_patch_template.yaml",
    "iac_drift_pr_expert": "llm/iac_drift_pr_template.yaml",
}

templates = {}
for key, path in template_paths.items():
    with open(path, 'r') as file:
        prompt_template = yaml.safe_load(file)
        templates[key] = prompt_template

llm = LLM(ollama_endpoint, api_key, prompt_templates=templates)


while True:
    print("Checking for IaC drift...")
    # perform drift detection logic here
    scans = drift_detection_engine.run_all_paths_terraform_plan()
    #print(f"Drift detection scans: {scans}")
    drifts = drift_detection_engine.resources_drift(scans)
    for environment in drifts:
        for path in drifts[environment]:
            drifted_resources = drifts[environment][path]['drifted_resources']
            prior_resources = drifts[environment][path]['prior_resources']
            # print(f"Drifted Resources: {drifted_resources}")
            # print(f"Prior Resources: {prior_resources}")

            print("Generating initial recommendations...")
            recommendations = llm.initial_recommendation(
                model=model,
                drift_scan = drifted_resources,
                watch=watch
            )
            print("Refining recommendations with second pass...")
            #filtered prior resources
            matching_prior_resources = drift_detection_engine.get_matching_prior_resources(
                drifted_resources=drifted_resources,
                prior_resources=prior_resources
            )
            refined_recommendations = llm.refine_recommendation(
                model=model,
                previous_response=recommendations,
                prior_state_root_module=matching_prior_resources,
            )

            #loop through the recommendations - right now the recommendations is a stringified list
            print(refined_recommendations)
            refined_recommendations_list = yaml.safe_load(refined_recommendations)

            for recommendation in refined_recommendations_list:
                if recommendation.get('fix_type') == 'code_patch':
                    print(f"Generating code update patch for {environment} at path {path}...")
                    patch = llm.fix_drift_patch(model=model, recommendation=recommendation, directory=path)
                    print(f"Generated Patch: {patch}")

                    #refresh the terraform after applying the patch
                    print(f"Applying generated patch to files...")
                    drift_detection_engine.refresh_terraform_state(path)
                    print(f"Patch is {patch}")
                    patch_json = json.loads(patch)
                    modified_files = patch_json.get('modified_files', [])
                    if modified_files and len(modified_files) > 0:
                        print("Generating Github PR for the applied patch...")
                        pr_response = llm.make_drift_pr(
                            model = model,
                            recommendation = recommendation,
                            directory = path,
                            modified_files = modified_files,
                            token = config.github_token
                        )

                        print(f"PR Response: {pr_response}")

            print(f"Refined Recommendations for environment '{environment}' at path '{path}':")
            print(refined_recommendations)

    print(f"Waiting for {drift_interval} seconds before next drift check...")

    time.sleep(drift_interval)



