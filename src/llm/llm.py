import json
import ast
import yaml
from openai import OpenAI
import sys
import os

from tools.apply_patch import *
from tools.discover_resource_files import *

class LLM:
    def __init__(self, api_endpoint: str, api_key: str, prompt_templates:dict):
        self.api_endpoint = api_endpoint
        self.api_key = api_key
        self.prompt_templates = prompt_templates
        self.client = OpenAI(api_key=self.api_key, base_url=self.api_endpoint)
    
    def format_prompt_with_template(self, template_name:str, placeholders: dict):
        if template_name not in self.prompt_templates:
            raise ValueError(f"Template {template_name} not found in prompt templates.")
        
        # get the prompt template from the dictionary then use the first key
        first_key = next(iter(self.prompt_templates[template_name]))
        template = self.prompt_templates[template_name][first_key]
        
        prompt_template = template

        # replace the placeholders in the template with actual values
        messages = []
        for message in prompt_template:
            if message["role"] == "user":
                content = message["content"].format(**placeholders)
            else:
                content = message["content"]

            messages.append({
                "role": message["role"],
                "content": content
            })
        
        #print("Formatted Messages:", messages)
        return messages
    

    def initial_recommendation(self, model, drift_scan: dict, watch: dict):
        placeholders = {
            "iac_scan_result": json.dumps(drift_scan, indent=2),
            "watch": json.dumps(watch, indent=2)
        }
        prompt = self.format_prompt_with_template("iac_drift_expert", placeholders)
        return self.chat(model=model, messages=prompt)
    
    def refine_recommendation(self, model, previous_response: str, prior_state_root_module: dict):
        placeholders = {
            "previous_drift_response": previous_response,
            "prior_state_root_module": json.dumps(prior_state_root_module, indent=2)
        }
        prompt = self.format_prompt_with_template("iac_drift_expert_second_pass",placeholders)
        return self.chat(model=model, messages=prompt)
    
    def fix_drift_patch(self, model, recommendation, directory:str):
        placeholders = {
            "recommendation": recommendation,
            "directory": directory
        }
        tools = self.register_tools()
        prompt = self.format_prompt_with_template("iac_drift_patch_expert", placeholders)

        executed_call_ids = set()  # Keep track of executed tool call IDs

        # Loop to handle multiple tool calls sequentially
        while True:
            message, tool_calls = self.chat(model=model, messages=prompt, tools=tools)

            # No more tool calls? return the LLM's final response
            if not tool_calls:
                return message.content

            # Execute all tool calls
            for call in tool_calls:
                # Skip already executed calls
                if call.id in executed_call_ids:
                    continue

                print(f"Call: {call.function.name}, Args: {call.function.arguments}")
                name = call.function.name
                args = json.loads(call.function.arguments)
                print(f"Executing tool call: {name} with args: {args}")

                # Map tools to actual functions
                if name == "discover_terraform_files":
                    result = discover_terraform_files(**args)
                elif name == "read_file":
                    result = read_file(**args)
                elif name == "write_file":
                    write_file(**args)
                    result = {"status": "ok"}  # indicate write succeeded
                else:
                    result = {"error": "Tool not recognized."}

                # Append tool result with proper tool_call_id
                prompt.append({
                    "role": "tool",
                    "tool_call_id": call.id,
                    "content": json.dumps(result, indent=2)
                })

                # Mark call as executed to avoid re-executing
                executed_call_ids.add(call.id)
    

    
    def chat(self, model, messages, tools: list = None, tool_choice:str="auto"):
        if tools:
            response = self.client.chat.completions.create(
                model=model,
                messages=messages,
                tools=tools,
                tool_choice=tool_choice
            )
            message = response.choices[0].message
            tool_calls = getattr(message, "tool_calls", None)
            return message, tool_calls
        
        response = self.client.chat.completions.create(
            model=model,
            messages=messages
        )
        return response.choices[0].message.content
    
    # fixed: add self to method definition
    def register_tools(self):
        return [
            {
                "type": "function",
                "function": {
                    "name": "discover_terraform_files",
                    "description": "Scan directory for Terraform resource definitions and return mapping",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "directory": {"type": "string", "description": "Path to directory to scan"}
                        },
                        "required": ["directory"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "read_file",
                    "description": "Read the contents of a file",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "file_path": {"type": "string"}
                        },
                        "required": ["file_path"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "write_file",
                    "description": "Write text content to a file",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "file_path": {"type": "string"},
                            "content": {"type": "string"}
                        },
                        "required": ["file_path", "content"]
                    }
                }
            }
        ]




# # load in the drift json file
# filename = "drift.json"

# with open(filename, "r") as f:
#     raw = f.read()
#     try:
#         drift_data = json.loads(raw)  # Try proper JSON first
#     except json.JSONDecodeError:
#         drift_data = ast.literal_eval(raw)  # Fallback for Python dict
    
#     #drift_data = drift_data.get('resource_drift', [])

# #selected only the resources drifted from the prior state
# resource_drifts = drift_data.get('resource_drift', [])

# prior_states = drift_data.get('prior_state')['values']['root_module']['resources']
# # print("prior_states loaded:", prior_states)
# # exit(0)

# #get the prior resources that match the drifted resources
# selected_prior_states = []
# for resource in resource_drifts:
#     address = resource.get('address')
#     for prior in prior_states:
#         if prior.get('address') == address:
#             selected_prior_states.append(prior)
#             break






# prompt_templates = {}
# prompt_template_filename = "iac_drift_template.yaml"
# with open(prompt_template_filename, "r") as f:
#     prompt_template = yaml.safe_load(f)
#     prompt_templates["iac_drift_expert"] = prompt_template

# with open("iac_drift_template_second_pass.yaml", "r") as f:
#     prompt_template = yaml.safe_load(f)
#     prompt_templates["iac_drift_expert_second_pass"] = prompt_template


# #print("Prompt Template Loaded:", prompt_template)

# ollama_endpoint = "http://localhost:11434/v1"
# api_key = "fake_api_key_for_ollama"
# llm = LLM(ollama_endpoint, api_key, prompt_templates=prompt_templates)

# #model = "llama3.1:latest"
# #model = "gpt-oss:20b"
# model = "qwen3-coder"

# #import the config from 1 directory up
# ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
# Config_path = os.path.join(ROOT_DIR, "config.yaml")
# schema = os.path.join(ROOT_DIR, "required_schema.yaml")
# sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# #print("Config Path:", Config_path)
# from config.config import Config
# config = Config(Config_path, schema)
# config.load()

# watch = config.environments
# formatted_prompt = llm.format_prompt_with_template(
#     current_chunk=drift_data,
#     watch=watch,
#     previous_chunk={}
# )
# response = llm.chat(model=model, messages=formatted_prompt)
# print("LLM Response:")
# print(response)

# print(drift_data.get('prior_state')['values']['root_module'])
# exit(0)

# drift_data = [
#   {
#     "address": "module.web.aws_instance.web_server",
#     "mode": "managed",
#     "type": "aws_instance",
#     "name": "web_server",
#     "provider_name": "registry.opentofu.org/hashicorp/aws",
#     "change": {
#       "actions": ["update"],
#       "before": {
#         "ami": "ami-0abc12345",
#         "instance_type": "t2.micro",
#         "tags": {
#           "Environment": "staging"
#         },
#         "vpc_security_group_ids": ["sg-00112233"],
#         "key_name": "old-key"
#       },
#       "after": {
#         "ami": "ami-0def67890",
#         "instance_type": "t2.small",
#         "tags": {
#           "Environment": "staging",
#           "Owner": "DevOpsTeam"
#         },
#         "vpc_security_group_ids": ["sg-00112233", "sg-44556677"],
#         "key_name": "new-key"
#       },
#       "after_unknown": {},
#       "before_sensitive": {},
#       "after_sensitive": {}
#     }
#   },
#   {
#     "address": "aws_security_group.db",
#     "mode": "managed",
#     "type": "aws_security_group",
#     "name": "db",
#     "provider_name": "registry.opentofu.org/hashicorp/aws",
#     "change": {
#       "actions": ["update"],
#       "before": {
#         "ingress": [
#           {
#             "from_port": 3306,
#             "to_port": 3306,
#             "protocol": "tcp",
#             "cidr_blocks": ["10.0.0.0/24"]
#           }
#         ],
#         "tags": {
#           "Environment": "production"
#         }
#       },
#       "after": {
#         "ingress": [
#           {
#             "from_port": 3306,
#             "to_port": 3306,
#             "protocol": "tcp",
#             "cidr_blocks": ["10.0.0.0/16"]
#           },
#           {
#             "from_port": 5432,
#             "to_port": 5432,
#             "protocol": "tcp",
#             "cidr_blocks": ["10.0.1.0/24"]
#           }
#         ],
#         "tags": {
#           "Environment": "production",
#           "Owner": "DBTeam"
#         }
#       },
#       "after_unknown": {},
#       "before_sensitive": {},
#       "after_sensitive": {}
#     }
#   }
# ]

# drift_data = [
#     {
#         "address": "aws_s3_bucket.untracked_bucket",
#         "mode": "managed",
#         "type": "aws_s3_bucket",
#         "name": "untracked_bucket",
#         "provider_name": "registry.opentofu.org/hashicorp/aws",
#         "change": {
#             "actions": ["create"],
#             "before": None,
#             "after": {
#                 "bucket": "untracked-bucket-prod",
#                 "acl": "private",
#                 "versioning": {"enabled": True},
#                 "tags": {"Environment": "Production", "Owner": "DevOpsTeam"},
#                 "region": "us-east-1"
#             },
#             "after_unknown": {"arn": True, "id": True}
#         },
#         "after_sensitive": {},
#         "before_sensitive": {}
#     },
#     {
#         "address": "aws_instance.orphan_instance",
#         "mode": "managed",
#         "type": "aws_instance",
#         "name": "orphan_instance",
#         "provider_name": "registry.opentofu.org/hashicorp/aws",
#         "change": {
#             "actions": ["create"],
#             "before": None,
#             "after": {
#                 "ami": "ami-0abcdef1234567890",
#                 "instance_type": "t2.medium",
#                 "tags": {"Environment": "Staging", "Owner": "QA"},
#                 "vpc_security_group_ids": ["sg-12345678"]
#             },
#             "after_unknown": {"arn": True, "id": True, "private_ip": True, "public_ip": True}
#         },
#         "after_sensitive": {},
#         "before_sensitive": {}
#     }
# ]


# inital_recommendations = llm.initial_recommendation(
#     model=model,
#     drift_scan=resource_drifts,
#     watch=watch
# )

# print(f"Initial Recommendations:{inital_recommendations}")

# refined_recommendations = llm.refine_recommendation(
#     model=model,
#     previous_response=inital_recommendations,
#     prior_state_root_module={"resources": selected_prior_states}
# )
# print(f"Refined Recommendations:{refined_recommendations}")
#print(drift_data.get('resource_drift', []))

# formatted_prompt = llm.format_prompt_with_template(
#     drift_data,
#     watch=watch
# )
# response = llm.chat(model=model, messages=formatted_prompt)
# print("LLM Response:")
# print(response)

#focus only on resource_changes key
# changes = drift_data.get("resource_changes", [])
# print(json.dumps(list(drift_data.keys()), indent=2))

# print(f"Length of resource_changes: {len(drift_data.get('resource_changes', []))}")
# print(f"Length of resource_drift: {len(drift_data.get('resource_drift', []))}")
# exit(0)
# print(changes[0])

# for change in changes:
#     print(change)
#     exit(0)
# print(drift_data["resource_changes"])
# exit(0)
# # Ensure drift_data is a dictionary before converting to list of items
# if isinstance(drift_data, dict):
#     drift_data = list(drift_data.items())
# else:
#     raise TypeError("drift_data must be a dictionary-like object containing key-value pairs.")

# # loop through the drift data in chunks in size that can support various llm context sizes. eg qwen3-coder:latest
# for i in range(0, len(drift_data), chunk_size):
#     current_chunk = drift_data[i:i + chunk_size]
#     current_chunk_dict = dict(current_chunk)  # Ensure it's a dict for JSON formatting
#     formatted_prompt = llm.format_prompt_with_template(
#         current_chunk=current_chunk_dict, 
#         watch=watch, 
#         previous_chunk=previous_chunks
#     )
#     response = llm.chat(model=model, messages=formatted_prompt)
#     responses.append(response)

#     if "chunk_incomplete: true" in response:
#         #maintain the last 10 chunks in previous_chunks
#         previous_chunks.extend(current_chunk)
#         previous_chunks = previous_chunks[-10:]

#     else:
#         previous_chunks = []

#     #print(f"Response for chunk {i//chunk_size + 1}:")
#     #print(response)

# print("All Responses:")
# for resp in responses:
#     print(resp)
