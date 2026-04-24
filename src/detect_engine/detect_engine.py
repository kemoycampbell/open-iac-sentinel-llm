import subprocess
import json
import shutil
from .terraform_parser import parse_drift_changes

class DriftDectionEngine:
    #TODO remove none
    def __init__(self, paths:dict = None, terraform_variant:str = "tofu"):
        self.paths = paths
        self.terraform_variant = terraform_variant

        #correct variant behavior if tflocal is used
        if self.terraform_variant == "tflocal":
            tflocal_path = shutil.which("tflocal")
            if tflocal_path is None:
                raise ValueError("tflocal is not installed or not found in PATH. Please install terraform-local and ensure it's in your system PATH.")
            self.terraform_variant = tflocal_path
    
    def run_all_paths_terraform_plan(self):
        results = {}
        for environment in self.paths:
            for path in environment.get('paths', []):
                print(f"Running terraform plan for environment: {environment}, path: {path}")
                result = self.run_terraform_plan(path)
                env = environment['name']
                if env not in results:
                    results[env] = {}
                results[env][path] = result
                #print(json.dumps(results, indent=2))
        return results
    
    # def parse_drift_changes(self, plan_output_json:dict):
    #     drifts = []

    #     #for all of the drifted resources, check the change and actions
    #     for resource in plan_output_json.get('resource_drift', []):
    #         change = resource.get('change', {})
    #         actions = change.get('actions', [])

    #         #we do not care about no-op changes
    #         if not actions or actions == ["no-op"]:
    #             continue

    #         before = change.get('before', {})
    #         after = change.get('after', {})

    #         print(f"before: {before}")
    #         print(f"after: {after}")

    #         exit(0)
    
    # def normalize_resources_drift(self, value):
    #     """
    #     Normalize the resources drift value so that it can be easily compared and analyzed
    #     """
        
    #     if value in [None, "", [], {}]:
    #         return None
        
    #     # normalize empty collections
    #     if isinstance(value, (list, dict)) and len(value) == 0:
    #         return None
        
    #     # recursive normalize
    #     if isinstance(value, list):
    #         normalized_list = [self.normalize_resources_drift(v) for v in value]

    #         # remove None entries from list (prevents noise like empty objects)
    #         cleaned_list = [v for v in normalized_list if v is not None]

    #         return cleaned_list or None
        
    #     if isinstance(value, dict):
    #         normalized_dict = {
    #             k: self.normalize_resources_drift(v) for k, v in value.items()
    #         }

    #         # remove keys with None values (KEY FIX: prevents null vs {} drift noise)
    #         cleaned_dict = {
    #             k: v for k, v in normalized_dict.items() if v is not None
    #         }

    #         return cleaned_dict or None
        
    #     return value
    
    # def is_effective_change(self,before, after):
    #     """
    #     Determine if the change between before and after is effective (i.e., not just a meaningless change)
    #     This can be used to filter out changes that are not relevant for drift detection
    #     """
    #     before = self.normalize_resources_drift(before)
    #     after = self.normalize_resources_drift(after)

    #     #print(f"Comparing before: {before} with after: {after}")

    #     return before != after
    
    # def get_relevant_changes(self, before, after):
    #     """
    #     This is used to extract out the relevant changes and keys that we would need.
    #     We also ignore irrelevant fields that are known as noise or empheral
    #     """

    #     IGNORE_FIELDS = [
    #         "public_ip",
    #         "public_dns",
    #         "tags",
    #         "tags_all",
    #         "timeouts",
    #         "metadata",
    #     ]

    #     before = self.normalize_resources_drift(before)
    #     after = self.normalize_resources_drift(after)

    #     diff = {}

    #     #extract all keys from both before and after
    #     keys = set(before.keys()) | set(after.keys())

    #     for key in keys:
    #         #skip irrelevant keys
    #         if key in IGNORE_FIELDS:
    #             continue
    #         before_value = before.get(key)
    #         after_value = after.get(key)
    #         if before_value != after_value:
    #             diff[key] = {
    #                 "before": before_value,
    #                 "after": after_value
    #             }
                
    #     return diff


    
    
    # def filter_resource_drift(self, drifted_resources: list):
    #     """
    #     Filter the drifted resources to only include those that have effective changes
    #     This can help focus on the most relevant drifts and reduce noise in the analysis
    #     """

    #     resources_changes = []

    #     #go through all resources and see if there are effective changes
    #     for resource in drifted_resources:
    #         actions = resource.get('change', {}).get('actions', [])

    #         #ignore empty changes and no-ops
    #         if not actions or actions == ["no-op"]:
    #             continue
            
    #         before = resource.get('change', {}).get('before')
    #         after = resource.get('change', {}).get('after')
    #         #print all keys

    #         # print(f"Not normalized Before: {before}, After: {after}")

    #         #track all effective changes
    #         if self.is_effective_change(before, after):
    #             #resources_changes.append(resource)
    #             diff = self.get_relevant_changes(before, after)
    #             resource = {
    #                 "address": resource.get('address'),
    #                 "type": resource.get('type'),
    #                 "actions": actions,
    #             }
    #             if diff:
    #                 #merge diff into resource for context on what changed
    #                 resource.update(diff)
    #             resources_changes.append(resource)
    #             # print(f"Effective change detected for resource {resource.get('address')}")
    #             # print(self.normalize_resources_drift(resource))
    #             # exit(0)
        
    #     #show all effective changes after filtering
    #     # for change in resources_changes:
    #     #     print(f"Effective change for resource {change.get('address')}: {json.dumps(change, indent=2)}")
    #     # exit(0)
    #     return resources_changes 

    # def flatten_child_modules(self, child_modules: list):
    #     flat_resources = []
        
    #     #base case
    #     if not child_modules:
    #         return flat_resources

    #     for module in child_modules:
    #         # extract resources at this level
    #         if 'resources' in module and module['resources']:
    #             for resource in module['resources']:
    #                 #print(f"flatten: {resource['address']}")
    #                 flat_resources.append(resource)

    #         # recurse into nested child modules
    #         if 'child_modules' in module and module['child_modules']:
    #             #print("\n\n\n")
    #             #print(f"nested child modules found: {module['child_modules']}")
    #             flat_resources.extend(
    #                 self.flatten_child_modules(module['child_modules'])
    #             )

    #     return flat_resources
                


    # def resources_drift(self, terraform_plan_scans: dict):
    #     drifts = {}
    #     for environment in terraform_plan_scans:
    #         for path in terraform_plan_scans[environment].keys():
    #             plan = terraform_plan_scans[environment][path]
    #             drifted_resources = plan.get('resource_drift')
    #             prior_resources = plan.get('prior_state')

    #             #we only want to analyze drifts if there are drifted resources and prior resources to compare against
    #             if prior_resources and drifted_resources:
    #                 #handle root module vs child module resources
    #                 prior_resources = prior_resources['values']['root_module']
    #                 if "child_modules" in prior_resources and prior_resources['child_modules']:
    #                     prior_resources = prior_resources['child_modules']
    #                     # print(f"child modules: {prior_resources}")
    #                     # exit(0)
    #                     # for prior_resource in prior_resources:
    #                     #     print(prior_resource)
    #                     #     print("\n")
    #                     prior_resources = self.flatten_child_modules(prior_resources)
    #                     #print(f"flattened child modules: {prior_resources}")

    #                     #print(f"child modules: {prior_resources}")
    #                     #exit(0)
    #                 else:
    #                     prior_resources = prior_resources['resources']
    #             if environment not in drifts:
    #                 drifts[environment] = {}

    #             drifts[environment][path] = {
    #                 'drifted_resources': drifted_resources,
    #                 'prior_resources': prior_resources
    #             }
    #     return drifts
    
    # def get_matching_prior_resources(self, drifted_resources: list, prior_resources: list):
    #     prior_map = {prior_resource.get("address"): prior_resource for prior_resource in prior_resources}

    #     return {
    #         "resources": [
    #             prior_map[resource["address"]]
    #             for resource in drifted_resources
    #             if resource.get("address") in prior_map
    #         ]
    #     }
    

    def get_drifted_resources(self, plan_outout_json:dict):
        drifts = plan_outout_json.get('resource_drift', [])
        #print(drifts)
        return parse_drift_changes(drifts)

    
    def run_terraform_plan(self, path:str):
        output_plan_file = "tfplan_detect"
        # run the plan with --detailed-exitcode to capture changes and --refresh=true to detect drift
        output_plan_args = f"-out={output_plan_file}"
        command = f"{self.terraform_variant} plan -detailed-exitcode -refresh-only {output_plan_args} -no-color"
        print(f"Running terraform plan for path: {path} with command: {command}")
        plan = subprocess.run(
            command,
            cwd=path,
            capture_output=True, 
            text=True
            )
        
        if plan.returncode == 1:
            raise RuntimeError(f"Terraform plan failed with error: {plan.stderr}")
        
        #ignore meaningless changes
        stdout = plan.stdout.strip().lower()
        #print(f"Terraform plan output for path {path}: {stdout}")
        if "no changes" in stdout:
            return {
                "resource_drift": [],
                "prior_state": {}
            }
    

        
        
        #show plan as json
        #command = [self.terraform_variant, "show", "-json", output_plan_file]
        command = f"{self.terraform_variant} show -json {output_plan_file}"
        show_process = subprocess.run(
            command,
            cwd=path,
            capture_output=True, 
            text=True
            )
        if show_process.returncode != 0:
            raise RuntimeError(f"Terraform show failed with error: {show_process.stderr}")
        
        drift_info = json.loads(show_process.stdout)

        resources_drift = drift_info.get('resource_drift', [])
        resource_changes = drift_info.get('resource_changes', [])

        #if there is nothing in resource_drift, we can still have relevant information in resource_changes that can be used for drift detection and patch generation
        if not resources_drift:
            drift_info['resource_drift'] = resource_changes
        
        return drift_info

    def refresh_terraform_state(self, path:str, target_resource:str):
        #command = [self.terraform_variant, "refresh", "-no-color"]
        # terraform apply -refresh-only -target=aws_instance.example

        # first we will try to run a apply refresh only for the specific resource
        command = f"{self.terraform_variant} apply -refresh-only -target={target_resource} -no-color"
        print(f"Running terraform refresh for path: {path} with command: {command}")

        try:
            refresh = subprocess.run(
                command,
                cwd=path,
                capture_output=True, 
                text=True
                )
        except Exception as e:
            return {
                "status": "error",
                "exit_code": -1,
                "stdout": "",
                "stderr": str(e)
            }

        # we will now check if the refresh was successful for that particular by looking at the plan
        command = f"{self.terraform_variant} plan -refresh-only -detailed-exitcode -no-color -target={target_resource}"
        print(f"Running terraform plan for path: {path} with command: {command}")
        refresh = subprocess.run(
            command,
            cwd=path,
            capture_output=True, 
            text=True
            )
    
        if refresh.returncode == 0:
            
            return {
                "status": "clean",
                "exit_code": 0,
                "stdout": refresh.stdout,
                "stderr": refresh.stderr
            }

    
        
        #have not completed resolved
        # - we have 2 cases for this, it is okay to still have changes if we have not processed all recommendations
        # - but if we have processed all recommendations and we still have changes, then it means the patch did not work
        if refresh.returncode == 2:
            return{
                "status": "drift_remaining",
                "exit_code": 2,
                "stdout": refresh.stdout,
                "stderr": refresh.stderr
            }


        # returncode == 1 has error
        return {
            "status": "error",
            "exit_code": 1,
            "stdout": refresh.stdout,
            "stderr": refresh.stderr
        }

