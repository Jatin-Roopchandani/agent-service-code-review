import asyncio
import argparse
import json
import os
from typing import Dict, Any

from google.adk.runners import InMemoryRunner
from agent import CodeReviewAgent


async def run_agent(pr_url: str) -> Dict[str, Any]:
    """Run the code review agent with the provided PR URL."""
    
    # Create agent instance
    agent = CodeReviewAgent()
    
    # Create runner
    runner = InMemoryRunner(app_name="code_review", agent=agent)
    
    # Create session with PR URL in state
    session = await runner.session_service.create_session(
        app_name="code_review",
        user_id="user",
        state={"pr_url": pr_url}
    )
    
    # Run the agent
    result = None
    async for event in runner.run_async(
        user_id="user",
        session_id=session.id,
        new_message={"role": "user", "parts": [{"text": f"Review PR: {pr_url}"}]}
    ):
        if hasattr(event, 'content') and event.content:
            result = event.content
    
    return result or {"success": False, "error": "No response from agent"}


def main():
    """Main entrypoint for the code review agent."""
    
    # Load environment variables from .env file if it exists
    env_file = os.path.join(os.path.dirname(__file__), '..', '.env')
    if os.path.exists(env_file):
        with open(env_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key.strip()] = value.strip()
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Code Review Agent")
    parser.add_argument("--pr-url", required=True, help="GitHub PR URL to review")
    
    args = parser.parse_args()
    
    # Run the agent
    try:
        result = asyncio.run(run_agent(args.pr_url))
        print(json.dumps(result, indent=2))
    except Exception as e:
        error_result = {
            "success": False,
            "error": f"Failed to run agent: {str(e)}",
            "clusters": None,
            "reviews": None,
            "summary": None
        }
        print(json.dumps(error_result, indent=2))


if __name__ == "__main__":
    main()