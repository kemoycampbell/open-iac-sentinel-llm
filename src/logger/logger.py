import json
import os
from datetime import datetime, timezone
import uuid
import traceback
from pathlib import Path
import hashlib


class LoggerSentinel:
    
    def __init__(self, even_log_file_name = None, failure_log_file_name = None):

        #we will take the filenames otherwise we default to sentinel_event_log.jsonl and sentinel_failure_log.jsonl
        self.event_log_file_name = even_log_file_name
        self.failure_log_file_name = failure_log_file_name

        #if the files were not provided, we will set the path to the root of the project in sentinel_logs directory
        #the root is two level up from the logger file, so we will use os.path to navigate to the root and then create a sentinel_logs directory if it does not exist
        sentinel__log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "sentinel_logs")
        if not self.event_log_file_name:
            self.event_log_file_name = os.path.join(sentinel__log_dir, "sentinel_event_log.jsonl")
            self.create_directory_if_not_exists(self.event_log_file_name)

        if not self.failure_log_file_name:
            self.failure_log_file_name = os.path.join(sentinel__log_dir, "sentinel_failure_log.jsonl")
            self.create_directory_if_not_exists(self.failure_log_file_name)
        
        #create a patch tracker -  this is acceptable for the thesis
        self.patch_tracker_file = os.path.join(sentinel__log_dir, "patch_tracker.json")
        self.create_directory_if_not_exists(self.patch_tracker_file)
        self.patches = self.get_patches()


    def create_directory_if_not_exists(self, file_path):
        directory = os.path.dirname(file_path)
        if not os.path.exists(directory):
            Path(file_path).parent.mkdir(parents=True, exist_ok=True)

    def _utc_now_iso(self):
        #normalize the timestamp to utc iso format to make it easier for analysis and avoid timezone issues
        return datetime.now(timezone.utc).isoformat()
    
    def generate_event_id(self):
        return str(uuid.uuid4())

    def normalize_log_json(self, log_entry):
        if isinstance(log_entry, str):
            try:
                return json.loads(log_entry)
            except json.JSONDecodeError:
                return log_entry
        elif isinstance(log_entry, list):
            return [self.normalize_log_json(item) for item in log_entry]
        elif isinstance(log_entry, dict):
            return {key: self.normalize_log_json(value) for key, value in log_entry.items()}
        return log_entry
    
    def log_drift_event(self, model,environment, path, resource, attribute, patch_context,correct_method, opensentinel_method, refresh_clean):
        log_entry = {
            "event_id": self.generate_event_id(),
            "timestamp": self._utc_now_iso(),
            "model": model,
            "environment": environment,
            "path": path,
            "resource": resource,
            "attribute": attribute,
            "patch_context": self.normalize_log_json(patch_context),
            "correct_method": correct_method,
            "opensentinel_method": opensentinel_method,
            "refresh_clean": refresh_clean
        }
        try:
            with open(self.event_log_file_name, 'a', encoding='utf-8') as file:
                file.write(json.dumps(log_entry) + '\n')
        except Exception as e:
            print(f"Error occurred while logging drift event: {e}")
            pass # for now we dont want the logging failure to stop the system from working. Maybe a log should add here to track when this fail.
    
    def log_orchestration_failure(self, environment,path,model,stage, error, llm_patch_context=None, recommendation=None):
        log_entry = {
            "failure_id": self.generate_event_id(),
            "timestamp": self._utc_now_iso(),
            "environment": environment,
            "path": path,
            "model": model,
            "stage": stage,
            "error_type": type(error).__name__,
            "error_message": str(error),
            "stack_trace": traceback.format_exc(),
        }

        if llm_patch_context:
            log_entry["llm_patch_context"] = self.normalize_log_json(llm_patch_context)

        if recommendation:
            log_entry["recommendation"] = self.normalize_log_json(recommendation)

        try:
            with open(self.failure_log_file_name, 'a', encoding='utf-8') as file:
                file.write(json.dumps(log_entry) + '\n')
        except Exception as e:
            print(f"Error occurred while logging orchestration failure: {e}")
            pass # for now we dont want the logging failure to stop the system from working. Maybe a log should add here to track when this fail.
        
        
    
    def normalize_patch_value(self, value):
        if isinstance(value, str):
            value = value.strip().lower()

            if value.isdigit():
                return int(value)
            if value == "true":
                return True
            if value == "false":
                return False
        
        if value == "" or value == {} or value == []:
            return None
        if isinstance(value, list):
            return [self.normalize_patch_value(v) for v in value]
        
        if isinstance(value, dict):
            return {
                k: self.normalize_patch_value(value[k])
                for k in sorted(value.keys())
            }
        return value

    # a temmp local caching methods for pending patches - in real implementations, we would check some type of database that get update through webhook or similar
    def get_patch_signature(self,path, model,drift):
        address = drift.get('address')
        attribute_path = drift.get('attribute_path')
        old_value = self.normalize_patch_value(drift.get('before'))
        new_value = self.normalize_patch_value(drift.get('after'))


        #take out only what we want from the drift as there are more attributes in it
        #sort the key to preserve the determistic order and remote whitespaces

        payload = json.dumps({
            "path": path,
            "address": address,
            "attribute_path": attribute_path,
            "old_value": old_value,
            "new_value": new_value,
            "model": model
        }, sort_keys=True, separators=(',', ':'))

        

        print(f"Generated payload for patch signature payload: {payload}")
        signature = hashlib.sha256(payload.encode('utf-8')).hexdigest()
        print(f"Generated patch signature: {signature}")
        
        return signature


    def get_patches(self):
        if not os.path.exists(self.patch_tracker_file):
            return {}
        with open(self.patch_tracker_file, 'r', encoding='utf-8') as file:
            try:
                return json.load(file)
            except json.JSONDecodeError:
                return {}
    
    def is_patch_exist(self,path, model,drift):
        patch_signature = self.get_patch_signature(path, model,drift)
        return patch_signature in self.patches
    
    def save_patch(self, environment, path, model, drift):
        patch_signature = self.get_patch_signature(path, model,drift)
        self.patches[patch_signature] = {
            "environment": environment,
            "path": path,
            "model": model,
            "resource": drift.get('address'),
            "attribute": drift.get('attribute_path'),
            "old_value": drift.get('before'),
            "new_value": drift.get('after'),
            "timestamp": self._utc_now_iso()
        }
        with open(self.patch_tracker_file, 'w', encoding='utf-8') as file:
            json.dump(self.patches, file, indent=2)