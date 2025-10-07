import os
import yaml
from pathlib import Path

class Config:
    def __init__(self, config_path: str):
        if not os.path.exists(config_path):
            raise FileNotFoundError(f"Configuration file not found: {config_path}")
        
        self.config_path = Path(config_path)
        self.config = self.__load_config()

    def __load_config(self) -> dict:
        with open(self.config_path, 'r') as file:
            return yaml.safe_load(file)


    def validate_config(self, required_keys: dict, config: dict = None, parent_path: str = "") -> bool:
        config = config or self.config

        for key, expected in required_keys.items():
            full_path = f"{parent_path}.{key}" if parent_path else key

            if key not in config:
                raise KeyError(f"Missing required key: {full_path}")

            value = config[key]

            if isinstance(expected, dict):
                if not isinstance(value, dict):
                    raise TypeError(f"Expected dict for key: {full_path}, got {type(value).__name__}")
                self.validate_config(expected, value, parent_path=full_path)
            elif isinstance(expected, type):
                if not isinstance(value, expected):
                    raise TypeError(f"Expected {expected.__name__} for key: {full_path}, got {type(value).__name__}")
            else:
                raise ValueError(f"Invalid schema definition for key: {full_path}. Expected a type or dict.")

        return True


@property
def config(self) -> dict:
    return self.config

@property
def llm(self) -> dict:
    return self.config.get('llm')

@property
def environments(self) -> dict:
    return self.config.get('environments')

@property
def drift_detection(self) -> dict:
    return self.config.get('drift_detection')


