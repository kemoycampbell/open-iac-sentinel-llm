import json
import ast
import yaml
from openai import OpenAI
import sys
import os

from tools.apply_patch import *
from tools.discover_resource_files import *
from tools.github import *

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
    
    def execute_tool_calls(self, tool_calls, tool_maps: dict, execute_calls_ids,execute_step, messages):
        for i, call in enumerate(tool_calls):
            # parse out the info from the tool call
            name = call.function.name
            args = json.loads(call.function.arguments)
            key = call.id  # use call.id to prevent duplicate execution

            # skip already executed calls
            if key in execute_calls_ids or name in execute_step:
                continue

            # mark the call as executed
            execute_calls_ids.add(key)
            execute_step.add(name)

            #debug
            # print(f"\n=== TOOL CALL {i+1} ===")
            # print(f"Tool ID: {call.id}")
            # print(f"Tool Name: {name}")
            # print(f"Tool Args: {args}")
            # print("\nCurrent messages before tool execution:")
            # for msg in messages:
            #     print(msg)
            # print("\n---------------------------\n")

            # map tools to actual functions
            func = tool_maps.get(name)
            if func:
                try:
                    result = func(**args)
                    if not result:
                        result = {"status": "ok"}  # indicate success for void functions
                except Exception as e:
                    result = {"error": f"Tool {name} failed with args: {args} with error: {str(e)}"}
            else:
                result = {"error": "Tool not recognized."}

            #Debug
            # print(f"Tool Execution Result for {name}:")
            # print(json.dumps(result, indent=2))

            # append tool result with proper tool_call_id
            messages.append({
                "role": "tool",
                "tool_call_id": call.id,
                "tool_name": name,
                "content": json.dumps(result, indent=2)
            })

            #debug
            # print(f"Tool message appended to messages for {name}:")
            # print(messages[-1])
            # print("\n===========================\n")
        return messages

            





    
    def make_drift_pr(self,model, recommendation: str, directory:str, token:str, modified_files: list):
        placeholders = {
            "recommendation": recommendation,
            "directory": directory,
            "token": token,
            "modified_files": modified_files
        }

        tools = self.register_PR_tools()
        prompt = self.format_prompt_with_template("iac_drift_pr_expert", placeholders)

        executed_calls = set()  # Keep track of executed tool call IDs
        executed_steps = set()  # Keep track of executed tool call names

        #create a map of the tools name based on their functions
        tool_maps = {
            "list_drifted_prs": list_drifted_prs,
            "stage_change": stage_change,
            "commit_change": commit_change,
            "push_change": push_change,
            "find_main_branch": find_main_branch,
            "find_repo_name_and_owner": find_repo_name_and_owner,
            "create_branch": create_branch,
            "delete_branch": delete_branch,
            "create_pr": create_pr
        }

        while True:
            message, tool_calls = self.chat(model=model, messages=prompt, tools=tools)
            #print("LLM Message:", message)
            prompt.append(message)
            # No more tool calls? return the LLM's final response
            if not tool_calls:
                return message.content
            # Execute all tool calls
            prompt = self.execute_tool_calls(tool_calls, tool_maps, executed_calls, executed_steps, prompt)

    
    

    def fix_drift_patch(self, model, llm_patch_context:dict):
            placeholders = {
                "llm_patch_context": llm_patch_context
            }
            tools = self.register_tools()
            prompt = self.format_prompt_with_template("iac_drift_patch_expert", placeholders)

            executed_call_ids = set()  # Keep track of executed tool call IDs
            executed_steps = set()

            #tool mapping
            tool_maps = {
                "read_file": read_file,
                "write_file": write_file
            }

            #sorta wanna prevent a run away model
            MAX_STEPS = 10
            steps = 0                    

            while True:
                steps += 1                    
                if steps > MAX_STEPS:         
                    raise RuntimeError("LLM did not produce final patch JSON")

                message, tool_calls = self.chat(
                    model=model,
                    messages=prompt,
                    tools=tools
                )

                
                if tool_calls:
                    prompt = self.execute_tool_calls(
                        tool_calls,
                        tool_maps,
                        executed_call_ids,
                        executed_steps,
                        prompt
                    )
                    continue                 
                
                # fix where the model sometime ends too early so we checks if the content is the final JSON we expect or if its just the model response before calling the tool. If its not the final JSON we expect we continue the loop and ask the model to try again.
                content = (message.content or "").strip()   

                if content.startswith("{") and "modified_files" in content:
                    return content            

                prompt.append(message)          


    
    def chat(self, model, messages, tools: list = None, tool_choice:str="required"):
        if tools:
            response = self.client.chat.completions.create(
                model=model,
                messages=messages,
                tools=tools,
                tool_choice=tool_choice
            )
            message = response.choices[0].message
            tool_calls = getattr(message, "tool_calls", None)
            # print(tool_calls)
            return message, tool_calls
        
        response = self.client.chat.completions.create(
            model=model,
            messages=messages
        )
        return response.choices[0].message.content
    
    
    def register_tools(self):
        return [
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
    
    def register_PR_tools(self):
        LLM_PR_TOOLS = [
        {
            "type": "function",
            "function": {
                "name": "list_drifted_prs",
                "description": "Retrieve a list of open pull requests filtered by labels to check for existing drift PRs.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "repo": {"type": "string", "description": "The GitHub repository name (e.g., 'my-repo')"},
                        "token": {"type": "string", "description": "GitHub personal access token for authentication"},
                        "owner": {"type": "string", "description": "The GitHub repository owner or organization (e.g., 'my-org')"},
                        "labels": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "List of labels to filter PRs"
                        }
                    },
                    "required": ["repo", "token", "labels", "owner"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "stage_change",
                "description": "Stage files for commit in the specified repository directory.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "repo_dir": {"type": "string", "description": "Path to the local repository"},
                        "files": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "List of file paths to stage"
                        }
                    },
                    "required": ["repo_dir", "files"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "commit_change",
                "description": "Commit staged changes in the repository with a message.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "repo_dir": {"type": "string", "description": "Path to the local repository"},
                        "message": {"type": "string", "description": "Commit message"}
                    },
                    "required": ["repo_dir", "message"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "push_change",
                "description": "Push a branch to the remote repository, setting upstream if needed.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "repo_dir": {"type": "string", "description": "Path to the local repository"},
                        "branch": {"type": "string", "description": "Branch name to push"}
                    },
                    "required": ["repo_dir", "branch"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "find_main_branch",
                "description": "Find the current branch of the repository (usually 'main' or 'master').",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "repo_dir": {"type": "string", "description": "Path to the local repository"}
                    },
                    "required": ["repo_dir"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "find_repo_name_and_owner",
                "description": "Return the GitHub repository owner and name from the local repository remote URL.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "repo_dir": {"type": "string", "description": "Path to the local repository"}
                    },
                    "required": ["repo_dir"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "create_branch",
                "description": "Create a new branch from a base branch and pull the latest changes.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "repo_dir": {"type": "string", "description": "Path to the local repository"},
                        "base_branch": {"type": "string", "description": "Branch to base the new branch on"},
                        "new_branch": {"type": "string", "description": "Name of the new branch"}
                    },
                    "required": ["repo_dir", "base_branch", "new_branch"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "delete_branch",
                "description": "Delete a local branch in the specified repository directory.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "repo_dir": {"type": "string", "description": "Path to the local repository"},
                        "branch": {"type": "string", "description": "Name of the branch to delete"}
                    },
                    "required": ["repo_dir", "branch"]
                }
            }
        }
        ,
        {
            "type": "function",
            "function": {
                "name": "create_pr",
                "description": "Create a pull request on GitHub.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "repo": {"type": "string", "description": "Repository name"},
                        "owner": {"type": "string", "description": "Repository owner or organization"},
                        "token": {"type": "string", "description": "GitHub personal access token"},
                        "title": {"type": "string", "description": "PR title"},
                        "body": {"type": "string", "description": "PR description"},
                        "head": {"type": "string", "description": "Branch containing the changes"},
                        "base": {"type": "string", "description": "Branch to merge into, e.g., 'main'"}
                    },
                    "required": ["repo", "owner", "token", "title", "body", "head", "base"]
                }
            }
        }
    ]
        return LLM_PR_TOOLS




