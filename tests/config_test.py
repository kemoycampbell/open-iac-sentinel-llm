from distutils.command import config
import pytest
from src.config.config import Config

@pytest.fixture
def sample_config(tmp_path):
    config = tmp_path / "config.yaml"
    config.write_text("""

# LLM configuration
llm:
  provider: ollama
  model: qwen
  endpoint: http://localhost:11434
  api_key_env_var: OLLAMA_API_KEY

# Watch configuration
watch:
  environments:
    - name: production
      paths:
        - ./terraform/production/vms
        - ./terraform/production/networking
      resources:
        includes:
          - aws_instance.web_server
          - aws_vpc_*
        excludes:
          - aws_instance.db_server
    - name: staging
      paths:
        - ./terraform/staging/*
      resources:
        includes:
          - aws_instance.staging_web
          - aws_vpc_staging_*
        excludes:
          - aws_instance.db_server
# Drift configuration
drift_detection:
  interval_seconds: 300

# Output configuration
output:
  log_level: info
  log_file: /var/log/drift_detection.log
""") 
    return config

@pytest.fixture
def sample_schema(tmp_path):
    schema = tmp_path / "required_schema.yaml"
    schema.write_text("""
llm:
  provider: str
  model: str
  endpoint: str
  api_key_env_var: str
watch:
  environments:
    type: list
    items:
      name: str
      paths: list
drift_detection:
  interval_seconds: int
output:
  log_level: str
  log_file: str                  
""")
    return schema



@pytest.fixture
def loaded_config(sample_config, sample_schema):
    config = Config(config_path=sample_config, required_schema_path=sample_schema)
    config.load()
    return config

def test_get_provider(loaded_config):
    assert loaded_config.get("llm.provider") == "ollama"

def test_get_environments(loaded_config):
    environments = loaded_config.get("watch.environments")
    assert isinstance(environments, list)
    assert environments[0]["name"] == "production"
    assert environments[1]["name"] == "staging"
    

                      