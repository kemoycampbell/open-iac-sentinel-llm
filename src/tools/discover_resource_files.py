import os
import re
import hcl2

MODULE_BLOCK_REGEX = r'module\s+"[^"]+"\s*{([^}]*)}'
SOURCE_REGEX = r'source\s*=\s*"([^"]+)"'
RESOURCE_BLOCK_REGEX = r'resource\s+"([^"]+)"\s+"([^"]+)"'
VARIABLE_USAGE_REGEX = r'\bvar\.([a-zA-Z_][a-zA-Z0-9_\.]*)'
MODULE_INPUT_REGEX = r'(\w+)\s*=\s*var\.([a-zA-Z_][a-zA-Z0-9_\.]*)'

VARIABLE_BLOCK_REGEX = r'variable\s+"([^"]+)"\s*{([^}]*)}'
DEFAULT_REGEX = r'default\s*=\s*(.+)'


#we want to use this to decide the priority of where to modify
SOURCE_PRIORITY = {
    "tfvars": 1,
    "default": 2,   # default values in variables.tf( lower priority than tfvars because tfvars often override defaults)
    "resource": 3
}


# it is possible for the directory to have a nested structures with internal directories containing .tf files
# we need to recursively search for all .tf files in the directory and its subdirectories
# it is also possible the modules are defined upwards so we also need to traverse upward
def discover_terraform_files(directory):
    resource_map = {}

    visited_dirs = set()

    # extract module sources from module blocks
    def extract_module_sources(content):
        module_blocks = re.findall(
            MODULE_BLOCK_REGEX,
            content,
            re.DOTALL
        )

        sources = []
        for block in module_blocks:
            match = re.search(SOURCE_REGEX, block)
            if match:
                sources.append(match.group(1))
        return sources

    # resolve local module paths (can point upward like ../..)
    def resolve_module_path(source, current_dir):
        if os.path.isabs(source):
            return source
        return os.path.abspath(os.path.join(current_dir, source))

    # recursively scan directories (including modules)
    def scan_directory(directory):
        directory = os.path.abspath(directory)

        if directory in visited_dirs:
            return
        visited_dirs.add(directory)

        if not os.path.isdir(directory):
            return

        try:
            for root, dirs, files in os.walk(directory):
                # skip terraform internal directory
                dirs[:] = [d for d in dirs if d != ".terraform"]

                for file in files:
                    if not (file.endswith('.tf') or file.endswith('.tfvars')):
                        continue

                    file_path = os.path.join(root, file)

                    if file_path in resource_map:
                        continue

                    with open(file_path, "r", encoding="utf-8") as f:
                        content = f.read()

                        # find all resource blocks
                        resource_blocks = re.findall(RESOURCE_BLOCK_REGEX, content)
                        resources = [
                            f"{resource_type}.{resource_name}"
                            for resource_type, resource_name in resource_blocks
                        ]

                        # extract variables used in .tf files
                        variables_used = list(set(re.findall(VARIABLE_USAGE_REGEX, content)))

                       #parse out variables assigned in .tfvars files
                        variables_assigned = {}

                        is_tfvars = file.endswith('.tfvars') or 'tfvars' in file

                        if is_tfvars:
                            try:
                                parsed_hcl = hcl2.loads(content)

                                # flatten safely (keeps structure instead of breaking it)
                                variables_assigned = parsed_hcl if parsed_hcl else {}

                            except Exception:
                                # fallback to empty if parsing fails
                                variables_assigned = {}

                        # detect module files (heuristic: contains module blocks)
                        is_module_file = bool(re.search(r'\bmodule\s+"', content))

                        # store structured metadata instead of raw list
                        resource_map[file_path] = {
                            "resources": resources,
                            "variables_used": variables_used,
                            "variables_assigned": variables_assigned,
                            "is_tfvars": is_tfvars,
                            "is_module_file": is_module_file
                        }

                        #add in default variables from variables.tf file or similar
                        if file.endswith('.tf') and not is_tfvars:
                            default_variables = extract_variable_defaults(content, file_path)
                            resource_map[file_path].setdefault("variable_defaults", {})
                            resource_map[file_path]["variable_defaults"].update(default_variables)

                        if is_module_file:
                            module_entries = []
                            module_blocks = re.findall(r'module\s+"([^"]+)"\s*{([^}]*)}', content, re.DOTALL)
                            for module_name, block_body in module_blocks:
                                inputs = dict(re.findall(MODULE_INPUT_REGEX, block_body))
                                module_entries.append({
                                    "module": f"module.{module_name}",
                                    "inputs": inputs
                                })
                            if module_entries:
                                resource_map[file_path]["module_inputs"] = module_entries


                        # follow module blocks (this is what allows "upward" discovery)
                        module_sources = extract_module_sources(content)
                        for source in module_sources:
                            if source.startswith("./") or source.startswith("../") or source.startswith("/"):

                                module_path = resolve_module_path(source, root)

                                # recursively scan discovered module paths
                                scan_directory(module_path)

        except PermissionError:
            # skip directories we cannot access
            return

    # start only from given directory
    scan_directory(directory)

    return {"resource_map": resource_map}

from collections import defaultdict


def normalize_terraform_states(resource_map):
    variables = {}
    resources = {}
    module_variable_aliases = defaultdict(dict)

    # extract the relevant components

    # first pass we will extract the tfvars files to get the variables
    for path, metadata in resource_map.items():
        extract_variables_from_tfvars(path, metadata, variables)
    
    #first b - fixing the priority where we make tfvars win instead of variables.tf default
    for path, meta in resource_map.items():
        for name, data in meta.get("variable_defaults", {}).items():
            # tfvars wins over defaults
            if name not in variables:
                variables[name] = data

    
    #second pass we will extract the resources and bind the variables to the resources in the impact graph
    for path, metadata in resource_map.items():
        for resource in metadata.get("resources", []):
            #extract the resources
            extract_resources(path, resource, resources)
    
    #third pass we will extract the module variable aliases which can help us bind the variables to the resources in the impact graph
    for path, meta in resource_map.items():
        for entry in meta.get("module_inputs", []):
            module_name = entry["module"]
            for input_name, root_var in entry["inputs"].items():
                module_variable_aliases[module_name][input_name] = root_var


    #fourth pass we will bind the variables to the resources in the impact graph
    for path, meta in resource_map.items():
        for resource in meta.get("resources", []):
            resource_module = resources[resource]["module"]
            aliases = module_variable_aliases.get(resource_module, {})

            for variable_used in meta.get("variables_used", []):
                rewritten = rewrite_variable_name(variable_used, aliases)
                bind_variables_to_resources(
                    variables,
                    rewritten,
                    resource
                )

    # return a focused structure for the LLM to reason about
    # instead of the lengthy raw resource map
    return {
        "variables": variables,
        "resources": resources,
    }



def rewrite_variable_name(variable_used, aliases):
    # use case for direct inputs example ssh_key
    if variable_used in aliases:
        return aliases[variable_used]

    # use case for module-local attribute like "ec2_config.instance_type"
    if "." in variable_used:
        _, attr = variable_used.split(".", 1)
        if attr in aliases:
            return aliases[attr]

    return variable_used



def extract_variables_from_tfvars(path, metadata, variables):
    #extract and flatten variables from tfvars
    if metadata.get("is_tfvars"):
        flatten_tfvars(
            metadata.get("variables_assigned", {}),
            variables,
            defined_in=path
        )
def extract_variable_defaults(content, path):
    defaults = {}
    variable_blocks = re.findall(VARIABLE_BLOCK_REGEX, content, re.DOTALL)

    for variable_name, block_body in variable_blocks:
        match = re.search(DEFAULT_REGEX, block_body)
        if match:
            defaults[variable_name] = {
                "value": match.group(1).strip(),
                "defined_in": path,
                "source": "default",
                "affects": [] 
            }
    return defaults


def extract_resources(path, resource, resources):
    value = {
        "defined_in": path,
        #infer module correctly from /modules/<name>/
        "module": infer_module_from_path(path),
        "attributes": {}
    }

    resources.setdefault(resource, value)


def bind_variables_to_resources(variables, variable_used, resource):
    # we will only bind variables that are actually used in the variables
    for existing_variable in variables:
        # matches var.x or nested var.x.y.z
        if (
            existing_variable == variable_used or
            existing_variable.startswith(f"{variable_used}.")
        ):
            impact = f"{resource}.*"

            # keep variable metadata consistent with impact_graph
            if impact not in variables[existing_variable]["affects"]:
                variables[existing_variable]["affects"].append(impact)



def infer_module_from_path(path):
    #infer the module based on the path
    components = path.replace("\\", "/").split("/")
    if "modules" in components:
        index = components.index("modules")
        if index + 1 < len(components):
            return f"module.{components[index + 1]}"

    return "root"


def flatten_tfvars(data, out, prefix="", defined_in=None):
    # loop through the data
    for key, value in data.items():
        # construct the full key based on the prefix, by default we assume no prefix
        full_key = key

        # correct our assumption
        if prefix:
            full_key = f"{prefix}.{key}"

        # we may need to recursively flatten nested structures
        if isinstance(value, dict):
            flatten_tfvars(
                value,
                out,
                prefix=full_key,
                defined_in=defined_in
            )
        else:
            out[full_key] = {
                "value": value,
                "defined_in": defined_in,
                "source": "tfvars",
                "affects": []  # populated during binding
            }

def parse_terraform_address(address):
    # we want to split the terraform address into module path, resource type, resource name and resource full qualified name

    if not address:
        return None
    components = address.replace("[", ".").replace("]", "").split(".")
    module_parts = []
    index = 0

    # a module can have many nested level so we will use a loop instead of a hard structture pattern
    while index < len(components) and components[index] == "module":
        # module.<name> or module.<name>.<index>
        module_parts.append(f"module.{components[index + 1]}")
        index+=2  # skip the module and its name
    
    #remaining should be resource type and name
    resource_type = components[index]
    resource_name = components[index + 1]
    resource__full_name = f"{resource_type}.{resource_name}"

    return {
        "module_path": module_parts,
        "resource_type": resource_type,
        "resource_name": resource_name,
        "resource_full_name": resource__full_name
    }


def extract_changed_fields(drifted_values):
    fields = set()

    #helper for change locality and handling of list and dic structure drift value
    for side in ("before", "after"):
        value = drifted_values.get(side)
        if isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    fields.update(item.keys())
        elif isinstance(value, dict):
            fields.update(value.keys())

    return fields

def variable_relevance_score(variable, changed_fields):
    score = 0
    for field in changed_fields:
        if field in variable:
            score += 1
    return score


    

def localize_change_area(resource_fqn, attribute,normalized_state, drifted_values,is_list_drift=False):
    #priority awared localization of area for change
    # - we grant highest priority to updates based on the order:
    # 1. variable updates
    #   1b. we priority tfvars over default values
    # 2. resource attribute updates
    
    candidates = []

    resource_short_name = resource_fqn.split(".")[-2] + "." + resource_fqn.split(".")[-1]
    changed_fields = extract_changed_fields(drifted_values)

    # 1. strict scalar attribute matching (when attribute exists)
    if attribute:
        for variable, meta in normalized_state.get("variables", {}).items():
            if variable != attribute and not variable.endswith(f".{attribute}"):
                continue

            if any(
                affected.startswith(resource_short_name)
                for affected in meta.get("affects", [])
            ):
                score = variable_relevance_score(variable, changed_fields)

                candidates.append({
                    "method": "variable_update",
                    "variable": variable,
                    "attribute": attribute,
                    "current_value": meta.get("value"),
                    "defined_in": meta.get("defined_in"),
                    "source": meta.get("source"),
                    "relevance": score,
                    "priority": SOURCE_PRIORITY.get(meta.get("source"), 99)
                })

    # 2. variable-backed locality for list / complex drifts
    
    before = drifted_values.get("before", [])
    after = drifted_values.get("after", [])

    is_addition = (
        isinstance(before, list) and
        isinstance(after, list) and
        any(item not in before for item in after)
    )

    if not candidates:
        for variable, meta in normalized_state.get("variables", {}).items():
            if not any(
                affected.startswith(resource_short_name)
                for affected in meta.get("affects", [])
            ):
                score = variable_relevance_score(variable, changed_fields)

                 # allow scalar list collections even if binding is indirect
                if not (
                    is_list_drift and
                    is_addition and
                    score == 0 and
                    attribute in variable
                ):
                    continue

            # list / complex drifts must have semantic overlap
            if is_list_drift:
                if is_addition:
                    # allow only collection variables related to the drifted attribute
                    if score > 0:
                        continue
                    if attribute not in variable:
                        continue


            candidates.append({
                "method": "variable_update",
                "variable": variable,
                "attribute": attribute,
                "current_value": meta.get("value"),
                "defined_in": meta.get("defined_in"),
                "source": meta.get("source"),
                "relevance": score,
                "priority": SOURCE_PRIORITY.get(meta.get("source"), 99)
            })

    # 3. resource fallback (always available)
    if resource_short_name in normalized_state.get("resources", {}):
        candidates.append({
            "method": "resource_attribute_update",
            "resource": resource_fqn,
            "attribute": attribute,
            "defined_in": normalized_state["resources"][resource_short_name]["defined_in"],
            "source": "resource",
            "relevance": 0,
            "priority": SOURCE_PRIORITY.get("resource", 99)
        })

    if not candidates:
        raise ValueError(
            f"No candidates found for localizing change area for resource {resource_fqn} and attribute {attribute}"
        )

    # prioritize: tfvars > default > resource, then semantic relevance
    candidates.sort(key=lambda x: (x["priority"], -x.get("relevance", 0)))
    return candidates[0]






def build_llm_patch_context(recommendation, drift, normalized_state):

    # print("\n\n")
    # print(f"Recommendation is: {recommendation}")
    # print("\n\n")
    # print(f"Drift is: {drift}")
    # print("\n\n")
    # print(f"Normalized state is: {normalized_state}")

    resource_fqn = drift["address"]
    is_list_drift = isinstance(drift.get("before"), list) or isinstance(drift.get("after"), list)
    resource = parse_terraform_address(resource_fqn)
    attribute = drift["attribute_path"]
    drifted_values = {
        "before": drift.get("before"),
        "after": drift.get("after")
    }



    change_area = localize_change_area(
        resource_fqn,
        attribute,
        normalized_state,
        drifted_values,
        is_list_drift=is_list_drift
    )


    return {
        "resource_full_qualified_name": resource.get("resource_full_name"),
        "drift_summary": recommendation.get("drift_type"),
        "drifted_values": drifted_values,
        "change_area": change_area
    }







