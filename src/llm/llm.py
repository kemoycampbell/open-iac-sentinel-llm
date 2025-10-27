from openai import OpenAI

class LLM:
    def __init__(self, api_endpoint: str, api_key: str, prompt_template:dict):
        self.api_endpoint = api_endpoint
        self.api_key = api_key
        self.prompt_template = prompt_template
        self.template_name = "iac_drift_expert"
        self.client = OpenAI(api_key=self.api_key, api_base=self.api_endpoint)
    
    def format_prompt_with_template(self, plan_output_json:dict, watch:dict):
        if self.template_name not in self.prompt_template:
            raise ValueError(f"Template {self.template_name} not found in prompt templates.")
        
        prompt_template = self.prompt_template[self.template_name]

        placeholders = {
            "iac_scan_resul": plan_output_json,
            "watch": watch
        }

        
        #user content
        user_content = prompt_template[1]["content"].format(**placeholders)

        #update the content in the prompt template
        prompt_template[1]["content"] = user_content

        return prompt_template
    
    def chat(self,model, messages):
        response = self.client.chat.completions.create(
            model=model,
            messages=messages
        )
        return response.choices[0].message.content
    
    

