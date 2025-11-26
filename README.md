# Overview
OpenSentinel is an open-source LLM-powered agent designed to detect and remediate Infrastructure-as-Code (IaC) drift in Terraform configurations. It leverages a user-defined LLM (configured in `config.yaml`) along with integrated tools to analyze Terraform files, identify drifts, generate patches, and create pull requests for remediation.

# Rationale
Infrastructure drift occurs when the actual state of infrastructure diverges from the declared state in IaC configurations. This can lead to inconsistencies, security vulnerabilities, and operational issues. OpenSentinel aims to automate the detection and remediation of such drifts using advanced language models, reducing manual effort and improving infrastructure reliability.

# Features
- **Configurable**: Easily configurable rules, preferred LLM model, repository to monitor and more via config.yaml
- **Drift Detection**: Analyze Terraform state files to identify configuration drifts between declared and actual(live) infrastructure.
- **Patch Generation**: Discover the locations of drifts in Terraform files and generate patches to remediate the drifts.
- **Pull Request Creation**: Automatically create pull requests with the generated patches for review and merging.
- **Tool Integration**: Integrated with various tools to discover resource maps, read, write to Terraform files as well as perform git operations to create pull requests.
  - **current implemented tools**:
  - discover_Terraform_files
  - read_file
  - write_file
  - find_repo_name_and_owner
  - list_drifted_prs
  - find_main_branch
  - create_branch
  - stage_change
  - commit_change
  - push_change
  - create_pr
  - delete_branch


# Warning
This is a active project and is under heavy development.

This project is currently a proof-of-concept to understand the capabilities of LLMs in the context of Infrastructure-as-Code drift detection and remediation. As it stands, it is not production-ready and should not
be used in production environments.

There are many changes need to be made before this can be considered production-ready which will be defined
in the research paper.

# Architecture Design
The architecture of OpenSentinel consists of the following key components:
1. **Detect Engine**: This is responsible for interacting with the Terraform state files and commands to get the
   `resource_drifts` resources, `prior_state` resources and other relevant information needed for drift detection.
   This component is capable of refreshing the Terraform state after the drift has been patched and more.
2. **LLM**: This component is responsible for interacting with the LLM model via the API. This component obtains the initial recommendations, perform a second pass recommendation to reduce hallucinations, provide tool calling capacities to patch the drifts, and create pull requests.
3. **iac_drift.py**: This is the main orchestrator that ties all the components together. It manages the continuous monitoring of the repositories, invokes the drift detection engine, interacts with the LLM for patch generation and pull request creation.

## High-Level Component Interaction Diagram

```mermaid
sequenceDiagram
    participant Main as iac_drift.py<br/>(Orchestrator)
    participant Config as Config<br/>(config.py)
    participant DetectEngine as DriftDetectionEngine<br/>(detect_engine.py)
    participant Terraform as Terraform CLI
    participant LLM as LLM<br/>(llm.py)
    participant LLMApi as LLM API<br/>(OpenAI Compatible)
    participant Tools as Tools<br/>(discover, apply_patch, github)
    participant GitHub as GitHub API

    Note over Main: Initialization Phase
    Main->>Config: Load config.yaml & required_schema.yaml
    Config->>Config: Validate configuration
    Config-->>Main: Return validated config
    Main->>DetectEngine: Initialize with environments & paths
    Main->>LLM: Initialize with endpoint, API key, templates

    Note over Main: Continuous Monitoring Loop
    loop Every drift_interval seconds
        Note over Main,Terraform: Drift Detection Phase
        Main->>DetectEngine: run_all_paths_terraform_plan()
        DetectEngine->>Terraform: terraform plan -detailed-exitcode -refresh=true
        Terraform-->>DetectEngine: Plan output
        DetectEngine->>Terraform: terraform show -json
        Terraform-->>DetectEngine: JSON plan with drift info
        DetectEngine-->>Main: Scan results with drift data

        Main->>DetectEngine: resources_drift(scans)
        DetectEngine-->>Main: Drifted resources & prior state

        alt Drift Detected
            Note over Main,GitHub: LLM Analysis & Remediation Phase
            Main->>LLM: initial_recommendation(drift_scan)
            LLM->>LLMApi: Chat completion with drift data
            LLMApi-->>LLM: Initial recommendations
            LLM-->>Main: Recommendation list

            Main->>DetectEngine: get_matching_prior_resources()
            DetectEngine-->>Main: Matching prior resources

            Main->>LLM: refine_recommendation(previous_response, prior_state)
            LLM->>LLMApi: Chat completion with prior state
            LLMApi-->>LLM: Refined recommendations
            LLM-->>Main: YAML recommendation list

            loop For each code_patch recommendation
                Note over Main,GitHub: Patch Generation Phase
                Main->>LLM: fix_drift_patch(recommendation, directory)
                LLM->>LLMApi: Chat with tools (discover, read, write)
                
                loop Tool execution cycle
                    LLMApi-->>LLM: Tool call request
                    LLM->>Tools: Execute tool (discover_terraform_files)
                    Tools-->>LLM: File mappings
                    LLM->>Tools: Execute tool (read_file)
                    Tools-->>LLM: File contents
                    LLM->>Tools: Execute tool (write_file)
                    Tools-->>LLM: Write confirmation
                    LLM->>LLMApi: Tool results
                end
                
                LLMApi-->>LLM: Final patch JSON
                LLM-->>Main: Generated patch with modified files

                Main->>DetectEngine: refresh_terraform_state(path)
                DetectEngine->>Terraform: terraform refresh
                Terraform-->>DetectEngine: Refreshed state
                DetectEngine-->>Main: Success

                Note over Main,GitHub: Pull Request Creation Phase
                Main->>LLM: make_drift_pr(recommendation, directory, files, token)
                LLM->>LLMApi: Chat with GitHub tools
                
                loop PR tool execution cycle
                    LLMApi-->>LLM: Tool call request
                    LLM->>Tools: find_repo_name_and_owner()
                    Tools-->>LLM: Repo info
                    LLM->>Tools: find_main_branch()
                    Tools-->>LLM: Main branch name
                    LLM->>Tools: create_branch()
                    Tools-->>LLM: New branch created
                    LLM->>Tools: stage_change()
                    Tools-->>LLM: Files staged
                    LLM->>Tools: commit_change()
                    Tools-->>LLM: Commit created
                    LLM->>Tools: push_change()
                    Tools-->>LLM: Changes pushed
                    LLM->>Tools: create_pr()
                    Tools->>GitHub: Create pull request
                    GitHub-->>Tools: PR created
                    Tools-->>LLM: PR URL
                    LLM->>LLMApi: Tool results
                end
                
                LLMApi-->>LLM: PR creation confirmation
                LLM-->>Main: PR response
            end
        end

        Main->>Main: Sleep for drift_interval seconds
    end
```

# Prequisites
 - A running LLM model. This is designed with privacy in mind, so you can run self hosted model such as ollama. However, the project utilize OpenAI's python's SDK so you are able to use any LLM models either self-hosted or commercial as long as they are compatible with OpenAI's python SDK.
 - Python 3+
 - Git installed and configured
 - Terraform installed and configured

# Getting Started
1. Clone the repository:
   ```bash
   git clone https://github.com/kemoycampbell/open-iac-sentinel-llm
   ```
2. Create a virtual environment and install dependencies:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows use `venv\Scripts\activate`
   pip install -r requirements.txt
   ```
3. Configure the application by creating `config.yaml`
   ```bash
   cp config.example.yaml config.yaml
   ```
4. Create and configure .env file with your LLM API keys and other sensitive information.
   ```bash
    cp env.example .env
    ```

4. Update `config.yaml` with your settings. You should specify:
   - LLM model and API key
   - List of repositories to monitor
     - infrastructure type such as production, staging, development, you can come up with any naming
     - paths to Terraform directories
     - list of resources to include or exclude from monitoring
   - Drift detection interval
  
  5. Run the application:
    ```bash
    cd src
    python iac_drift.py
    ```

# TODO
- [ ] Convert to threaded or asynchronous processing for monitoring multiple repositories concurrently.
- [ ] Implement logging and monitoring for better observability.
- [ ] Allow configurations of templates. This will allow user to bring in their own prompt templates
- [ ] Implement more robust error handling and retry mechanisms.
- [ ] Add support for more version control systems like GitLab, Bitbucket, etc.
- [ ] Refactor codebase for better modularity and maintainability.
- [ ] Implement unit and integration tests.
- [ ] Experiment with different approaches compare to purely prompt templated based
  
# License
This project is licensed under the MIT License - see the LICENSE file for details.

# Contributions
Contributions are welcome! Please open issues and submit pull requests for any features, bug fixes,
or improvements.



  