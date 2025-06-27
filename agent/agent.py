import json
import re
from typing import AsyncGenerator, Dict, Any, Optional
from urllib.parse import urlparse

from google.adk.agents import BaseAgent, LlmAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event

from tools.bash_tool import get_bash_tool
from tools.grep_tool import GrepTools


class CodeReviewAgent(BaseAgent):
    """Agent that automates GitHub PR code review process."""
    
    def __init__(self, name: str = "code_review_agent"):
        super().__init__(
            name=name,
            description="Automates GitHub PR code review by clustering diffs, reviewing each cluster, and posting summary comments"
        )
        
    def _validate_pr_url(self, pr_url: str) -> bool:
        """Validate PR URL format."""
        if not pr_url:
            return False
            
        try:
            parsed = urlparse(pr_url)
            if parsed.netloc != "github.com":
                return False
                
            # Check if path matches /owner/repo/pull/number pattern
            path_parts = parsed.path.strip("/").split("/")
            if len(path_parts) != 4 or path_parts[2] != "pull":
                return False
                
            # Check if PR number is valid
            try:
                int(path_parts[3])
            except ValueError:
                return False
                
            return True
        except Exception:
            return False
    
    def _create_error_response(self, error_message: str) -> Dict[str, Any]:
        """Create standardized error response."""
        return {
            "success": False,
            "error": error_message,
            "clusters": None,
            "reviews": None,
            "summary": None
        }
    
    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        """Main workflow implementation."""
        try:
            # Get PR URL from request
            pr_url = ctx.session.state.get("pr_url")
            if not pr_url:
                yield Event(content=self._create_error_response("No pr_url provided"))
                return
                
            # Validate PR URL
            if not self._validate_pr_url(pr_url):
                yield Event(content=self._create_error_response("Invalid pr_url format"))
                return
            
            # Step 1: Fetch and cluster PR diffs
            fetch_cluster_agent = LlmAgent(
                name="fetch_cluster",
                model="gemini-2.0-flash",
                description="Fetches PR diffs and clusters them into logical groups",
                instruction=f"""
                You are a code review assistant. Your task is to fetch the PR diffs from the GitHub URL and cluster them into logical groups.

                The PR URL is: {pr_url}

                Steps:
                1. Use the gh tool to fetch the PR diffs and metadata
                2. Clean up the diffs by removing unnecessary escape characters (like \\\\' for single quotes)
                3. Cluster the diffs into logical groups based on:
                   - Related functionality
                   - Similar file types
                   - Dependencies between changes
                4. For each cluster, provide:
                   - A descriptive name
                   - A brief description of what the cluster contains
                   - The list of files and their diffs in that cluster

                Output the result as a JSON object with this structure:
                {{
                    "clusters": [
                        {{
                            "name": "cluster_name",
                            "description": "Brief description of the cluster",
                            "files": [
                                {{
                                    "filename": "path/to/file.py",
                                    "diff": "cleaned diff content"
                                }}
                            ]
                        }}
                    ]
                }}

                Store the result in state with key 'base_clusters'.
                """,
                tools=get_bash_tool(["gh"], truncate_length=10000),
                output_key="base_clusters"
            )
            
            async for event in fetch_cluster_agent.run_async(ctx):
                yield event
            
            # Check if clustering was successful
            base_clusters = ctx.session.state.get("base_clusters")
            if not base_clusters:
                yield Event(content=self._create_error_response("No base_clusters found"))
                return
            
            # Parse clusters from the response
            try:
                if isinstance(base_clusters, str):
                    clusters_data = json.loads(base_clusters)
                else:
                    clusters_data = base_clusters
                    
                if "clusters" not in clusters_data:
                    yield Event(content=self._create_error_response("No clusters found"))
                    return
                    
                clusters = clusters_data["clusters"]
            except (json.JSONDecodeError, TypeError):
                yield Event(content=self._create_error_response("No clusters found"))
                return
            
            # Step 2: Review each diff cluster
            all_reviews = []
            grep_tools = GrepTools()
            
            for i, cluster in enumerate(clusters):
                review_agent = LlmAgent(
                    name=f"review_cluster_{i}",
                    model="gemini-2.0-flash",
                    description=f"Reviews cluster: {cluster.get('name', f'cluster_{i}')}",
                    instruction=f"""
                    You are a senior code reviewer. Review the following code cluster and provide detailed feedback.

                    Cluster: {cluster.get('name', f'cluster_{i}')}
                    Description: {cluster.get('description', 'No description')}
                    
                    Files in this cluster:
                    {json.dumps(cluster.get('files', []), indent=2)}

                    For each significant issue you find, provide:
                    1. The affected code snippet
                    2. The start line and end line of the snippet (estimate if not available)
                    3. A detailed explanation of the issue
                    4. Suggested improvements
                    5. Severity level (high, medium, low)

                    Focus on:
                    - Security vulnerabilities
                    - Performance issues
                    - Code quality and maintainability
                    - Best practices violations
                    - Potential bugs

                    Output as JSON:
                    {{
                        "cluster_name": "{cluster.get('name', f'cluster_{i}')}",
                        "reviews": [
                            {{
                                "code_snippet": "relevant code",
                                "start_line": 10,
                                "end_line": 15,
                                "issue": "detailed issue description",
                                "suggestion": "suggested improvement",
                                "severity": "high/medium/low"
                            }}
                        ]
                    }}

                    Store the result in state with key 'review_{i}'.
                    """,
                    tools=grep_tools.get_tools(),
                    output_key=f"review_{i}"
                )
                
                async for event in review_agent.run_async(ctx):
                    yield event
                
                # Collect the review
                review_result = ctx.session.state.get(f"review_{i}")
                if review_result:
                    try:
                        if isinstance(review_result, str):
                            review_data = json.loads(review_result)
                        else:
                            review_data = review_result
                        all_reviews.append(review_data)
                    except (json.JSONDecodeError, TypeError):
                        yield Event(content=self._create_error_response(f"Review failed for cluster {i}"))
                        return
                else:
                    yield Event(content=self._create_error_response(f"Review failed for cluster {i}"))
                    return
            
            # Step 3: Filter reviews
            filter_agent = LlmAgent(
                name="filter_reviews",
                model="gemini-2.0-flash",
                description="Filters reviews to remove non-actionable feedback",
                instruction=f"""
                You are a code review curator. Filter the following reviews to keep only actionable, valuable feedback.

                Reviews to filter:
                {json.dumps(all_reviews, indent=2)}

                Remove reviews that are:
                - Nitpicky or overly pedantic
                - Purely stylistic without clear benefit
                - Already handled by automated tools
                - Too vague or non-specific
                - Duplicate or redundant

                Keep reviews that are:
                - Security-related
                - Performance-impacting
                - Bug-causing
                - Maintainability-improving
                - Best practice violations with clear impact

                Output the filtered reviews as a formatted markdown string that will be posted as a PR comment.
                Use this format:

                ## Code Review Summary

                ### High Priority Issues
                [List high severity issues with code snippets and line numbers]

                ### Medium Priority Issues
                [List medium severity issues]

                ### Low Priority Issues
                [List low severity issues]

                ### Overall Assessment
                [Brief summary of the changes and overall quality]

                Store the result in state with key 'reviewed_review'.
                """,
                output_key="reviewed_review"
            )
            
            async for event in filter_agent.run_async(ctx):
                yield event
            
            # Check if filtering was successful
            filtered_review = ctx.session.state.get("reviewed_review")
            if not filtered_review:
                yield Event(content=self._create_error_response("Review filtering failed"))
                return
            
            # Step 4: Post summary comment
            post_comment_agent = LlmAgent(
                name="post_comment",
                model="gemini-2.0-flash",
                description="Posts the filtered review as a comment on the PR",
                instruction=f"""
                You need to post the following review comment to the GitHub PR: {pr_url}

                Review content:
                {filtered_review}

                Generate a single bash command that uses the gh CLI to post this comment to the PR.
                The command should properly escape the comment content for bash.

                Output only the bash command as a string, nothing else.
                Store the result in state with key 'output'.
                """,
                tools=get_bash_tool(["gh"], truncate_length=10000),
                output_key="output"
            )
            
            async for event in post_comment_agent.run_async(ctx):
                yield event
            
            # Check if comment posting was successful
            post_output = ctx.session.state.get("output")
            if not post_output:
                yield Event(content=self._create_error_response("Comment posting failed"))
                return
            
            # Create success response
            success_response = {
                "success": True,
                "clusters": clusters_data,
                "reviews": all_reviews,
                "summary": filtered_review,
                "error": None
            }
            
            yield Event(content=success_response)
            
        except Exception as e:
            yield Event(content=self._create_error_response(f"Unexpected error: {str(e)}"))