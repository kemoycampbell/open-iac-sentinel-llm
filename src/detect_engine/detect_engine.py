import subprocess
import json
import shutil
from .terraform_parser import parse_drift_changes

class DriftDectionEngine:
    def __init__(self, paths:dict = None, terraform_variant:str = "tofu"):
        self.paths = paths
        self.terraform_variant = terraform_variant

        #correct variant behavior if tflocal is used
        #tflocal is a great tool for local aws testing using localstack or other local emulators
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
        # if "no changes" in stdout and "your infrastructure still matches the configuration":
        #     return {
        #         "resource_drift": [],
        #     }
    

        
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
        
        print(f"Terraform show output for path {path}: {show_process.stdout[:500]}...")  # print the beginning of the output for debugging
        drift_info = json.loads(show_process.stdout)

        print(f"Keys in drift_info: {drift_info.keys()}")

        print(f"drifted resources: {drift_info.get('resource_drift', [])}")
        print(f"resource changes: {drift_info.get('resource_changes', [])}")
        print(f"planned values: {drift_info.get('planned_values', {})}")
        resources_drift = drift_info.get('resource_drift', [])
        resource_changes = drift_info.get('resource_changes', [])

        #if there is nothing in resource_drift, we can still have relevant information in resource_changes that can be used for drift detection and patch generation
        if not resources_drift:
            drift_info['resource_drift'] = resource_changes
        
        return drift_info

    def refresh_terraform_state(self, path:str, target_resource:str):
        #command = [self.terraform_variant, "refresh", "-no-color"]

        # we will now check if the operation was successful for that particular by looking at the plan
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

