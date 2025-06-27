## Overview
Build an agent (the 'code review' agent) that automates the process of reviewing a GitHub pull request by clustering diffs, reviewing each cluster, filtering reviews, and posting a summary comment on the PR.

**Note:** Bash tools and grep tools are already provided and available for use. For each step, use only the tools that are actually needed for that step—do not declare or pass extra tools that are not required. (For example, only pass `gh` to steps that fetch PR data, and grep tools to steps that analyze code.)

## Agent Structure Requirements
- Implement a single custom agent class (subclass of BaseAgent) that orchestrates the entire workflow.
- Inside this agent, each major step must be implemented as a separate LlmAgent instance:
  - Fetch and cluster PR diffs: LlmAgent with output_key="base_clusters" and only the tools needed for fetching (e.g., `gh`).
  - Review each diff cluster: LlmAgent with output_key="review" and only the tools needed for code review (e.g., grep tools).
  - Filter reviews: LlmAgent with output_key="reviewed_review" (no tools needed, just LLM filtering).
  - Post summary comment: LlmAgent with output_key="output" and only the tools needed for posting (e.g., `gh`).
- The workflow agent should run each LlmAgent in sequence, yielding events and checking for required state after each step, as in the resolve issue agent. Use an iterative, step-by-step approach, but only use iterations/loops where necessary (e.g., for reviewing each cluster).
- The main agent should yield events from each sub-agent and handle errors (e.g., check for required state after each step, yield error events if missing).
- Place all agent logic and workflow orchestration in `agent.py`.
- `main.py` should only contain a minimal entrypoint to run the agent (argument parsing, session initialization, running the agent). Do NOT put agent logic in main.py.

## User Workflow

### Input Requirements
The user provides:
- **PR URL**: A link to the GitHub pull request to be reviewed.

### Output Requirements
Return a JSON response containing:
- **Clusters** - The clustered diffs for the PR, with descriptions and file diffs.
- **Reviews** - The code review for each cluster, filtered for actionable feedback.
- **Summary** - The final comment posted to the PR.
- **Success** - Boolean indicating if the process completed successfully.
- **Error** - Error message if any step fails.

## Features

### Step 1: Fetch and Cluster PR Diffs
- Retrieve the diffs and metadata for the PR using the GitHub CLI (via the provided bash tools).
- Cluster the diffs into logical groups using the LLM.
- Implement this as a dedicated LlmAgent instance with output_key="base_clusters" 
- Clean up the diffs by removing any unnecessary escape characters (like \\\\' for single quotes)
- Structure the clusters into a well-defined JSON schema for downstream processing.

### Step 2: Review Each Diff Cluster
- For each cluster, review the code diffs using the LLM and grep tools as needed.
- Implement this as a dedicated LlmAgent instance with output_key="review"
- Iterate over all clusters, yielding events and collecting reviews.
- The output must include the affected code snippet, the start line and end line of the snippet and the details of the review

### Step 3: Filter Reviews
- Filter the reviews to remove non-actionable or non-useful feedback using the LLM.
- Implement this as a dedicated LlmAgent instance with output_key="reviewed_review".
- Output a review in the form of a string.

### Step 4: Post Summary Comment
- Collate the filtered reviews into a single markdown comment and post it to the PR using the GitHub CLI.
- Implement this as a dedicated LlmAgent instance with output_key="output".
- The esponse should be a single bash command only that posts the formatted comment to the PR.

## Error Handling
- The agent must validate the presence and format of the PR URL before proceeding. If the PR URL is missing or invalid, return a JSON response with `success: false` and `error: "No pr_url provided"` or `error: "Invalid pr_url format"`.
- If fetching or clustering diffs fails, return `success: false` and `error: "No base_clusters found"`.
- If structuring output fails, return `success: false` and `error: "No clusters found"`.
- If reviewing a cluster fails, return `success: false` and `error: "Review failed for cluster X"`.
- If filtering reviews fails, return `success: false` and `error: "Review filtering failed"`.
- If posting the summary comment fails, return `success: false` and `error: "Comment posting failed"`.
- For any other error, return a clear, specific error message in the `error` field and set `success: false`.
- In all error cases, fields that are not available due to the error (e.g., `clusters`, `reviews`, `summary`) should be null or omitted.


## Response Format
- Apply to `agent.py`

## Agent Behavior
- Accept requests with a PR URL.
- Validate input before proceeding.
- Return structured JSON responses.
- Include helpful error messages for invalid or failed steps.
- Use only the provided bash and grep tools for all codebase operations, and only the tools needed for each step.

## Environment Variables
- Requires access to GitHub CLI and repository.
- No external API keys required beyond GitHub authentication.

## Dependencies
- **Python** (for agent logic)
- **Bash tools**: `gh`, `git`
- **Grep tools** (for code analysis)
- **JSON** for response formatting 