import subprocess
import json

class DriftDectionEngine:
    #TODO remove none
    def __init__(self, paths:dict = None, terraform_variant:str = "tofu"):
        self.paths = paths
        self.terraform_variant = terraform_variant
    
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

    def resources_drift(self, terraform_plan_scans: dict):
        drifts = {}
        for environment in terraform_plan_scans:
            for path in terraform_plan_scans[environment].keys():
                plan = terraform_plan_scans[environment][path]
                drifted_resources = plan.get('resource_drift', [])
                prior_resources = plan.get('prior_state')['values']['root_module']['resources']
                if environment not in drifts:
                    drifts[environment] = {}

                drifts[environment][path] = {
                    'drifted_resources': drifted_resources,
                    'prior_resources': prior_resources
                }
        return drifts
    
    def get_matching_prior_resources(self, drifted_resources: list, prior_resources: list):
        matching_resources = []
        for resource in drifted_resources:
            address = resource.get('address')
            for prior in prior_resources:
                if prior.get('address') == address:
                    matching_resources.append(prior)
                    break
        return {"resources": matching_resources}

    
    def run_terraform_plan(self, path:str):
        output_plan_file = "tfplan_detect"
        # run the plan with --detailed-exitcode to capture changes and --refresh=true to detect drift
        output_plan_args = f"-out={output_plan_file}"
        command = [self.terraform_variant, "plan", "-detailed-exitcode", "-refresh=true", output_plan_args,"-no-color"]
        plan = subprocess.run(
            command,
            cwd=path,
            capture_output=True, 
            text=True
            )
        
        if plan.returncode == 1:
            raise RuntimeError(f"Terraform plan failed with error: {plan.stderr}")
        
        
        #show plan as json
        command = [self.terraform_variant, "show", "-json", output_plan_file]
        show_process = subprocess.run(
            command,
            cwd=path,
            capture_output=True, 
            text=True
            )
        if show_process.returncode != 0:
            raise RuntimeError(f"Terraform show failed with error: {show_process.stderr}")
        
        return json.loads(show_process.stdout)

    def refresh_terraform_state(self, path:str):
        command = [self.terraform_variant, "refresh", "-no-color"]
        refresh = subprocess.run(
            command,
            cwd=path,
            capture_output=True, 
            text=True
            )
        
        if refresh.returncode != 0:
            raise RuntimeError(f"Terraform refresh failed with error: {refresh.stderr}")
        
        return refresh.stdout
