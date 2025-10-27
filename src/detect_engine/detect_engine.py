import subprocess
import json

class DriftDectionEngine:
    #TODO remove none
    def __init__(self, paths:dict = None, terraform_variant:str = "tofu"):
        self.paths = paths
        self.terraform_variant = terraform_variant
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
    


#testing

master_plan = DriftDectionEngine()
path = '/home/cypher/Desktop/engineering-cloud-software-system/docker-wp'
drift_result = master_plan.run_terraform_plan(path)

print(drift_result)