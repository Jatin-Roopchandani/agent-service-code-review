from typing import AsyncGenerator

from google.adk.agents import BaseAgent, LlmAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event
from google.adk.models.lite_llm import LiteLlm
from google.genai import types
from typing_extensions import override

from patched_adk.tools.bash_tool import get_bash_tool
from patched_adk.tools.grep_tool import GrepTools

GPT_4O = LiteLlm("openai/gpt-4o")
CLAUDE_4 = LiteLlm("anthropic/claude-4-sonnet-20250514")
GEMINI_20_FLASH = "gemini-2.0-flash"
MODEL = CLAUDE_4


class ResolveIssueAgent(BaseAgent):
    @override
    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        if not ctx.session.state.get("issue_url"):
            yield Event(
                content=types.Content(
                    role="system", parts=[types.Part(text="No issue_url found in the session state")]
                ),
                author=self.name,
            )
            return

        # First get the issue details
        get_issue_details = LlmAgent(
            name="get_issue_details",
            model=MODEL,
            instruction="""
Get the issue details for the url "{issue_url}" using the github cli through bash tool.
Return the issue title and description.
            """,
            tools=get_bash_tool(["gh"], truncate_length=10000),
            output_key="issue_details",
        )

        ctx.branch = get_issue_details.name
        async for event in get_issue_details.run_async(ctx):
            yield event

        if "issue_details" not in ctx.session.state:
            yield Event(
                content=types.Content(
                    role="system", parts=[types.Part(text="No issue_details found in the session state")]
                ),
                author=self.name,
            )
            return

        # Analyze the issue and identify files to change
        analyze_issue = LlmAgent(
            name="analyze_issue",
            model=MODEL,
            instruction="""
You are a senior software engineer tasked to analyze an issue.
Your analysis will be used to guide the implementation of the fix.

Consider the following issue:

<issue_description>
{issue_url}
{issue_details}
</issue_description>

Let's first explore and analyze the repository to understand where the issue is located. Try to locate the specific files and code sections that need to be modified.

1. First explore the repo structure
2. Identify the relevant files that likely need changes
3. Once you've confirmed the error, identify the specific code sections that need to be modified

Provide your findings in this format:
<analysis>
    <file>file that needs changes</file>
    <changes_needed>Description of the specific changes needed</changes_needed>
</analysis>

Current working directory is the root of the repo, so paths for tools should be relative to the root of the repo.
            """,
            tools=GrepTools().get_tools(),
            output_key="analysis",
        )

        ctx.branch = analyze_issue.name
        async for event in analyze_issue.run_async(ctx):
            yield event

        if "analysis" not in ctx.session.state:
            yield Event(
                content=types.Content(role="system", parts=[types.Part(text="No analysis found in the session state")]),
                author=self.name,
            )
            return

        # Implement the changes
        implement_changes = LlmAgent(
            name="implement_changes",
            model=MODEL,
            instruction="""
You are a senior software engineer tasked to implement the changes to the codebase.
Consider the following issue:
<issue_description>
{issue_url}
{issue_details}
</issue_description>

Your lead engineer has already analyzed the issue and provided his analysis for you for reference.

<lead_analysis>
{analysis}
</lead_analysis>
<lead_instructions>
I've already taken care of all changes to any of the test files described in the PR.
This means you DON'T have to modify the testing logic or any of the tests in any way!
</lead_instructions>

Let's implement the necessary changes:
1. Edit the sourcecode of the repo to resolve the issue
2. Think about edge cases and make sure your fix handles them as well

Important Limitations:
1. DO NOT use command piping (|) - each command must be run independently
2. DO NOT use command chaining (&&, ||, ;) - each command must be run separately
3. DO NOT use redirection (> or >>) - output will be captured automatically
4. DO NOT use command substitution ($()) - commands must be run directly
5. For long files, the output of the command will be truncated to 10000 characters. Accordingly, you should use 'sed' to read parts of the file.

Guidelines for using these tools:
1. Always start by using 'ls' to check the current directory structure
2. Use 'find' with specific paths, not wildcards in the middle of paths (e.g., use 'find . -path "./opsdroid/connector/telegram/*" -name "*.py"')
3. Read file contents before making changes using 'cat' or 'sed'
4. Use 'grep' to locate specific code patterns that need modification
5. Use 'sed' for making precise text changes
6. Use 'wc' to check file sizes before reading
7. Use file operations (cp, mv, rm, mkdir, touch) when creating new files or restructuring

Remember to:
- Always verify changes after making them
- Handle edge cases appropriately
- Keep the changes focused and minimal
- Document your changes clearly
- Run each command independently without piping or chaining
- Start with simple commands like 'ls' to understand the directory structure before using more complex commands
            """,
            tools=get_bash_tool(
                [
                    "sed",
                    "cat",
                    "grep",
                    "find",
                    "ls",
                    "wc",
                    "cp",
                    "mv",
                    "rm",
                    "mkdir",
                    "touch",
                ],
                truncate_length=10000,
            ),
        )

        ctx.branch = implement_changes.name
        async for event in implement_changes.run_async(ctx):
            yield event

        # Create PR
        create_pr = LlmAgent(
            name="create_pr",
            model=MODEL,
            instruction="""
You are a senior software engineer creating a PR to fix an issue.
You have already implemented the changes to the codebase. Now your task is to stage the changes, commit them and create a PR.

The issue details are:
<issue_details>
{issue_url}
{issue_details}
</issue_details>

You have access to a bash tool that can be used to run `git` and `gh` commands.

1. Create a new branch with an appropriate branch name according to the issue details, with the prefix "patchwork-resolve-issue-".
2. Stage all the files and commit them with an appropriate commit message according to the issue details.
3. Push the branch to the remote repository.
4. Create a PR with same title as the commit message using github cli.

Then summarize your actions in a few sentences.
            """,
            tools=get_bash_tool(["gh", "git"], truncate_length=10000),
            output_key="pr_output",
        )

        ctx.branch = create_pr.name
        async for event in create_pr.run_async(ctx):
            yield event

        if "pr_output" in ctx.session.state:
            yield Event(
                content=types.Content(role="user", parts=[types.Part(text=ctx.session.state["pr_output"])]),
                author=self.name,
            )
            