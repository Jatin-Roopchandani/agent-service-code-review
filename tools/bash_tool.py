import asyncio
import subprocess
from textwrap import indent
from typing import Awaitable, Callable, List, Optional, Any, Coroutine

from patched_adk.config import truncate_str

from .logger import logger


def create_runtime_cli_tool(command: str, truncate_length: Optional[int] ):
    func_name = f"{command}_cli"
    func_docstring = f"""
\"\"\"
Run a {command}.
{f'Note: The output will be truncated to {truncate_length} characters, ending with {truncate_str} if it is longer than that.' if truncate_length else ''}

Args:
    args: The arguments to pass to the command.

Returns:
    The output of the {command}.
\"\"\"
"""
    func_text = f"""
async def {func_name}(args: list[str]) -> str:
{indent(func_docstring, '    ')}
    logger.info(f"bash_tool called with command: {command} {{args}}")
    process = await asyncio.create_subprocess_exec(
        '{command}',
        *args,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()
    if process.returncode != 0:
        err_msg = stderr.decode("utf-8")
        err_str = f"Command {command} {{args}} failed with return code {{process.returncode}} and stderr: {{err_msg}}"
        logger.error(err_str)
        return f"Error: {{err_str}}"
    output = stdout.decode("utf-8")
    if {truncate_length} and len(output) > {truncate_length}:
        output = output[:{truncate_length}] + truncate_str
    logger.info(f"bash_tool output: {{output}}")
    return output
    """
    code = compile(func_text, "<string>", "exec")
    space = dict()
    exec(code, globals(), space)
    print(space)
    return space[func_name]

def get_bash_tool(
    allowed_commands: Optional[List[str]] = None, truncate_length: Optional[int] = None
) -> list[Callable[[list[str]], Awaitable[str]]]:
    return [create_runtime_cli_tool(command, truncate_length) for command in allowed_commands]
