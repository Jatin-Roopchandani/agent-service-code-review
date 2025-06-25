import argparse
import asyncio
import logging
import os

from google.adk.runners import InMemoryRunner
from google.genai import types

from example_agents.logger import get_logger
from example_agents.resolve_issue.agent import ResolveIssueAgent

app_name = "resolve_issue"
user_id = "1234"

logging.basicConfig(level=logging.INFO)
logger = get_logger("resolve_issue")


def is_gh_authenticated():
    return os.system("gh auth status > /dev/null 2>&1; echo $?") == 0


def raise_if_checks_failed():
    errors = []
    if not is_gh_authenticated():
        errors.append("❌ GitHub is not authenticated, run `gh auth login` or set the GH_TOKEN environment variable")
    # if os.environ.get("OPENAI_API_KEY", None) is None:
    #     errors.append("❌ OPENAI_API_KEY is not set")

    if len(errors) > 0:
        raise ValueError("The following checks failed:\n" + "\n".join(errors))


async def main():
    raise_if_checks_failed()

    parser = argparse.ArgumentParser()
    parser.add_argument("--issue_url", type=str, required=True)
    args = parser.parse_args()

    if not args.issue_url:
        raise ValueError("issue_url is required")

    if not args.issue_url.startswith("https://github.com/"):
        raise ValueError("issue_url must start with https://github.com/")

    runner = InMemoryRunner(
        app_name=app_name,
        agent=ResolveIssueAgent(
            name="resolve_issue_agent",
        ),
    )
    session = await runner.session_service.create_session(
        app_name=app_name, user_id=user_id, state={"issue_url": args.issue_url}
    )

    async for event in runner.run_async(
        user_id=user_id,
        session_id=session.id,
        new_message=types.Content(role="user", parts=[types.Part(text="Follow the system instruction.")]),
    ):
        logger.info(event.model_dump_json(exclude_unset=True, exclude_defaults=True, exclude_none=True))


def run():
    asyncio.run(main())


if __name__ == "__main__":
    run()
