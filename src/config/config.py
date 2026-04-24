import os
import yaml
from pathlib import Path
from dotenv import load_dotenv

class Config:
    def __init__(self, config_path: str, required_schema_path: str, dotenv_path: str):
        self.config_path = Path(config_path)
        self.required_schema_path = Path(required_schema_path)
        self.dotenv_path = dotenv_path

        if not self.config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")
        if not self.required_schema_path.exists():
            raise FileNotFoundError(f"Schema file not found: {required_schema_path}")

        self._config = None
        self.required_schema = None

    def load(self):
        self._config = self._open_yaml(self.config_path)
        self.required_schema = self._open_yaml(self.required_schema_path)
        load_dotenv(self.dotenv_path)
        self.validate_config(self.required_schema, self._config)

    def _open_yaml(self, path: Path) -> dict:
        with open(path, 'r') as file:
            return yaml.safe_load(file)

    def get(self, path: str, default=None):
        keys = path.split('.')
        current = self._config
        for key in keys:
            if not isinstance(current, dict) or key not in current:
                return default
            current = current[key]
        return current

    def set(self, path: str, value: any):
        keys = path.split('.')
        current = self._config

        for key in keys[:-1]:
            if key not in current or not isinstance(current[key], dict):
                current[key] = {}
            current = current[key]

        final_key = keys[-1]
        current[final_key] = value

        # revalidate full config (safe option)
        self.validate_config(self.required_schema, self._config)

    def update(self, path: str, value: any):
        self.set(path, value)

    def save(self):
        with open(self.config_path, 'w') as file:
            yaml.safe_dump(self._config, file)

    def validate_config(self, required_keys: dict, config: dict, parent_path: str = "") -> bool:
        type_map = {"str": str, "int": int, "float": float, "bool": bool, "list": list, "dict": dict}

        for key, expected in required_keys.items():
            full_path = f"{parent_path}.{key}" if parent_path else key

            # Ensure key exists
            if key not in config:
                raise KeyError(f"Missing required key: {full_path}")

            value = config[key]

            # Case 1: Schema defines a dict with "type" (like type: list)
            if isinstance(expected, dict) and "type" in expected:
                expected_type_str = expected["type"]
                if expected_type_str not in type_map:
                    raise ValueError(f"Unknown type '{expected_type_str}' in schema for key: {full_path}")
                
                expected_type = type_map[expected_type_str]
                if not isinstance(value, expected_type):
                    raise TypeError(f"Expected {expected_type.__name__} for key: {full_path}, got {type(value).__name__}")

                # If it's a list with defined items
                if expected_type is list and "items" in expected:
                    for i, item in enumerate(value):
                        self.validate_config(expected["items"], item, parent_path=f"{full_path}[{i}]")
                continue

            # Case 2: Schema defines nested keys (no 'type' key)
            if isinstance(expected, dict):
                if not isinstance(value, dict):
                    raise TypeError(f"Expected dict for key: {full_path}, got {type(value).__name__}")
                self.validate_config(expected, value, parent_path=full_path)
                continue

            # Case 3: Schema defines string type name (e.g., "str")
            if isinstance(expected, str):
                if expected not in type_map:
                    raise ValueError(f"Unknown type '{expected}' in schema for key: {full_path}")
                if not isinstance(value, type_map[expected]):
                    raise TypeError(f"Expected {expected} for key: {full_path}, got {type(value).__name__}")
                continue

            # Case 4: Schema defines a direct Python type
            if isinstance(expected, type):
                if not isinstance(value, expected):
                    raise TypeError(f"Expected {expected.__name__} for key: {full_path}, got {type(value).__name__}")
                continue

            raise ValueError(f"Invalid schema definition for key: {full_path}. Expected a type, string, or dict.")

        return True


   
    @property
    def config(self) -> dict:
        return self._config

    @property
    def llm(self) -> dict:
        return self._config.get('llm')

    @property
    def environments(self) -> dict:
        return self._config.get('watch')

    @property
    def drift_detection(self) -> dict:
        return self._config.get('drift_detection')
    
    @property
    def github_token(self)-> str:
        return os.getenv('GITHUB_TOKEN')
    @property
    def llm_api_key(self) -> str:
        env_key = self.llm.get('api_key_env_var')
        return os.getenv(env_key)
    
    @property
    def terraform_variant(self) -> str:
        return self._config.get('terraform').get('variant')
    
    @property
    def log_path(self)-> str:
        return self._config.get('output').get('log_file')
    
    @property
    def failure_log_path(self)-> str:
        return self._config.get('output').get('failure_log_file')

