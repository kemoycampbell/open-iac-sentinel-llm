# a dictionary of fields to ignore when performing drift detections
# these are often fields that are expected to change and do not represent actual drift, for example, public IPs, timestamps, etc.
IGNORE_FIELDS = {
    "public_ip",
    "public_dns",
    "tags_all",
    "timeouts",
    "metadata",
}



def is_ignore_field(key):
    return key in IGNORE_FIELDS
def normalize_resources_drift(value):
    """
    Normalize the resources drift value so that it can be easily compared and analyzed
    """
    if value in [None, "", [], {}]:
        return None
    
    # normalize empty collections
    if isinstance(value, (list, dict)) and len(value) == 0:
        return None
    
    # recursive normalize
    if isinstance(value, list):
        normalized_list = [normalize_resources_drift(v) for v in value]

        # remove None entries from list (prevents noise like empty objects)
        cleaned_list = [v for v in normalized_list if v is not None]

        return cleaned_list or None
    
    if isinstance(value, dict):
        normalized_dict = {
            k: normalize_resources_drift(v) for k, v in value.items()
        }

        # remove keys with None values  prevents null vs {} drift noise)
        cleaned_dict = {
            k: v for k, v in normalized_dict.items() if v is not None
        }

        return cleaned_dict or None
    
    return value

def parse_drift_changes(drifts:list):
    actual_drifts = []
    for drift in drifts:
        print(f"Parsing drift: {drift.get('address')}")
        change = drift.get('change', {})
        actions = change.get('actions', [])

        #we do not care about no-op changes
        if not actions or actions == ["no-op"]:
            continue
        before = normalize_resources_drift(change.get('before', {}))
        after = normalize_resources_drift(change.get('after', {}))
        diff = diff_values(before, after)

        if not diff:
            continue

        #take care of list changes
        diff = collapse_list_diffs(diff)

        #we want our llm to focus on single changes at a time instead of throwing all in one go.
        #This will help will accuracy of code locality, target patched, targetd PR generation, and overall better explainability of the drift and recommended fix.
        for attribute_path, change in diff.items():
            item = {
                    "address": drift.get('address'),
                    "type": drift.get('type'),
                    "name": drift.get('name'),
                    "action": actions,
                    "attribute_path": attribute_path,
                    "before": change["before"],
                    "after": change["after"],
                }
            
            actual_drifts.append(item)

    return actual_drifts


def collapse_list_diffs(diff):
    # we want to be able to track hirerarchy of changes in lists, for example if we have a change in a list of security group rules, 
    # we want to be able to track that the change is in the second rule of the list instead of treating each attribute change as a separate change and losing the context of the rule it belongs to. 
    # So we will collapse changes that are in the same list item into one change with the path of the list item.
    parents = set()
    for path in diff:
        if "[" in path:
            parents.add(path.split("[", 1)[0])

    collapsed = {}
    for path, change in diff.items():
        parent = path.split("[", 1)[0]
        # keep leaf diffs when parent diff doesnt exist (edge case - s3 versioning is where i first spot this)
        if parent in parents and path!=parent and parent not in diff:
            collapsed[path] = change
            continue
        
        if parent in parents and path != parent:
            continue
        collapsed[path] = change

    return collapsed


def diff_values(before, after, path=""):
    # a leaf is considered any value that is not a dict or list
    if is_leaf(before, after):
        return diff_leaf(before, after, path)

    #recursively diff dicts and lists
    if is_dict_pair(before, after):
        return diff_dict(before, after, path)

    if is_list_pair(before, after):
        return diff_list(before, after, path)

    return {}

def diff_leaf(before, after, path):
    if before!= after and not is_ignore_field(path.split('.')[-1]):
        return {
            path: {
                "before": before,
                "after": after
            }
        }
    return {}

def diff_dict(before, after, path):
    changes = {}
    all_keys = set(before.keys()) | set(after.keys())

    for key in all_keys:
        if is_ignore_field(key):
            continue
        new_path = f"{path}.{key}" if path else key
        changes.update(diff_values(before.get(key), after.get(key), new_path))
    
    return changes

def diff_list(before, after, path):

    changes = {}

    for index, (b, a) in enumerate(zip(before, after)):
        next_path = f"{path}[{index}]"
        changes.update(diff_values(b, a, next_path))

    # If list length differs, treat whole list as changed
    if len(before) != len(after):
        changes[path] = {
            "before": before,
            "after": after
        }

    return changes


def is_leaf(before, after):
    return not isinstance(before, (dict, list)) or not isinstance(after, (dict, list))

def is_dict_pair(before, after):
    return isinstance(before, dict) and isinstance(after, dict)

def is_list_pair(before, after):
    return isinstance(before, list) and isinstance(after, list)

