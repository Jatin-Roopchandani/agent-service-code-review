# Code Review Agent

An automated GitHub PR code review agent built with Google ADK (Agent Development Kit) that analyzes pull requests, clusters diffs, performs intelligent code reviews, and posts actionable feedback.

## Features

- **Automated PR Analysis**: Fetches and analyzes GitHub PR diffs
- **Intelligent Clustering**: Groups related changes for focused review
- **Multi-step Review Process**: Reviews each cluster independently
- **Filtered Feedback**: Removes non-actionable comments and focuses on valuable insights
- **Automated Comments**: Posts structured review comments directly to the PR

## Agent Behavior

The agent performs a 4-step workflow:

1. **Fetch & Cluster**: Retrieves PR diffs via GitHub CLI and clusters related changes
2. **Review Clusters**: Performs detailed code review on each cluster focusing on:
   - Security vulnerabilities
   - Performance issues
   - Code quality and maintainability
   - Best practices violations
   - Potential bugs
3. **Filter Reviews**: Removes non-actionable feedback and keeps valuable insights
4. **Post Summary**: Creates and posts a structured markdown comment to the PR

## Installation

1. Install dependencies:
```bash
pip install -e .
```

2. Set up environment variables by copying and configuring the example file:
```bash
cp .env.example .env
# Edit .env with your API keys
```

3. Authenticate with GitHub CLI:
```bash
gh auth login
```

## Usage

Run the agent with a GitHub PR URL:

```bash
python agent/main.py --pr-url https://github.com/owner/repo/pull/123
```

## Environment Variables

The agent requires the following environment variables:

- `GEMINI_API_KEY`: Google Gemini API key for LLM operations
- `GITHUB_TOKEN`: GitHub token (optional if using `gh auth login`)

See `.env.example` for all configuration options.

## Response Format

The agent returns a JSON response with:

```json
{
  "success": true,
  "clusters": [...],     // Clustered PR diffs
  "reviews": [...],      // Detailed reviews for each cluster  
  "summary": "...",      // Final markdown comment posted to PR
  "error": null
}
```

## Error Handling

The agent handles various error scenarios:
- Invalid or missing PR URL
- GitHub API failures
- LLM processing errors
- Network connectivity issues

All errors return structured JSON responses with descriptive error messages.

## Dependencies

- **Google ADK**: Agent framework and LLM integration
- **LiteLLM**: Multi-model LLM interface
- **GitHub CLI**: PR data fetching and comment posting
- **Python 3.11+**: Runtime requirement