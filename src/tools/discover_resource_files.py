import json
import os
import re



#it is possible for the directory to have a nested structures with internal directories containing .tf files
#we need to recursively search for all .tf files in the directory and its subdirectories
def discover_terraform_files(directory):
    resource_map = {}
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith('.tf'):
                file_path = os.path.join(root, file)
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
                    #find all resource blocks
                    resource_blocks = re.findall(r'resource\s+"([^"]+)"\s+"([^"]+)"', content)
                    resources = []
                    for resource_type, resource_name in resource_blocks:
                        resources.append(f"{resource_type}.{resource_name}")
                    
                    #do not add empty resource files
                    if resources:
                        resource_map[file_path] = resources
    return {"resource_map": resource_map}


print(json.dumps(discover_terraform_files('C:/Users/kscics/Desktop/engineering-cloud-software-system/docker-wp'), indent=2))