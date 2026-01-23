import argparse
import json
import ollama
from typing import Dict, List, Set

# Import all utilities, tools, and helpers from utils.py
from utils import (
    # Display constants
    YOU_COLOR,
    ASSISTANT_COLOR,
    ERROR_COLOR,
    SUCCESS_COLOR,
    RESET_COLOR,
    # Tool registry and execution
    TOOL_REGISTRY,
    get_tool_str_representation,
    execute_tool,
    # Parsing
    extract_tool_invocations,
    # Display functions
    show_tool_result,
    get_multiline_input,
    # Loop detection
    get_action_signature,
    detect_loop,
    # Config and approval
    init_config,
    get_config,
    request_approval,
)


SYSTEM_PROMPT = """You are Qwen, a coding agent that completes tasks by calling tools.

TOOLS:
{tool_list_repr}

FORMAT: tool: tool_name({{'key': 'value'}})

RULES:
1. Call tools directly - no explanations
2. One tool per response - act immediately
3. For newlines in file content, use \\n
4. CRITICAL: Keep each file under 60 lines. If logic is complex, split into multiple small files.

MULTI-FILE PROJECTS:
If the task requires multiple files, create them in sequence before running.
Do NOT run code until all required files exist.
Break complex logic into small, focused files (20-60 lines each).

PARSE ERRORS:
If you get "missing closing parenthesis" or "Incomplete tool call":
- The file content is TOO LONG to parse
- Split the file into 2-3 smaller files instead
- Example: Instead of one 100-line algorithms.py, create bubble_sort.py, quick_sort.py, merge_sort.py

ERRORS:
- Read error messages - they contain line numbers
- view_file → fix with replace_lines → run again
- returncode=0 = success, stop editing

FILE PATHS:
Use explicit paths or __file__ in generated code."""


def get_full_system_prompt():
    """Generate the full system prompt with tool descriptions."""
    tool_str_repr = "\n\n".join(
        f"• {get_tool_str_representation(name)}"
        for name in TOOL_REGISTRY
    )
    return SYSTEM_PROMPT.format(tool_list_repr=tool_str_repr)


def execute_llm_call(conversation: List[Dict[str, str]]):
    """Execute an LLM call via Ollama."""
    response = ollama.chat(
        model="qwen2.5-coder:14b", # use your local Ollama model
        messages=conversation,
        options={
            "temperature": 0.0,
            "num_predict": 4096,
            "num_ctx": 8192,
            "stop": ["User:", "\n\nYou (type"],
        }
    )
    return response['message']['content']


def run_coding_agent_loop(auto_mode: bool = False):
    # Initialize config
    config = init_config(auto_mode=auto_mode)

    conversation = [{"role": "system", "content": get_full_system_prompt()}]
    MAX_STEPS = 50

    created_files: Set[str] = set()
    action_history: List[str] = []

    # Show startup message with mode indicator
    mode_str = f"{ASSISTANT_COLOR}AUTO{RESET_COLOR}" if config.is_auto_mode() else f"{SUCCESS_COLOR}MANUAL{RESET_COLOR}"
    print(f"{SUCCESS_COLOR}Coding Agent Ready{RESET_COLOR} [{mode_str} mode]")
    print(f"Type your request, then 'SUBMIT' to send.")
    if not config.is_auto_mode():
        print(f"{YOU_COLOR}Human approval required for file changes and commands.{RESET_COLOR}")
    print(f"Press Ctrl+C to exit.\n")

    while True:
        user_input = get_multiline_input()

        if user_input is None:
            print("\nExiting...")
            break
        if not user_input:
            continue

        conversation.append({"role": "user", "content": user_input})
        action_history.clear()
        error_history: List[str] = []
        consecutive_no_tool = 0

        for step in range(1, MAX_STEPS + 1):
            print(f"\n{ASSISTANT_COLOR}[Step {step}/{MAX_STEPS}]{RESET_COLOR}")

            response = execute_llm_call(conversation)

            # DEBUG: Show what LLM generated
            print(f"  {ASSISTANT_COLOR}LLM Response:{RESET_COLOR} {response[:200]}")

            tool_invocations, parse_error = extract_tool_invocations(response, TOOL_REGISTRY)

            if not tool_invocations:
                consecutive_no_tool += 1

                response_lower = response.lower()
                done_signals = ['task complete', 'finished creating', 'all files created', 'project is ready', 'done.']
                if any(sig in response_lower for sig in done_signals):
                    print(f"{SUCCESS_COLOR}Agent reports completion:{RESET_COLOR} {response[:200]}")
                    if created_files:
                        print(f"{SUCCESS_COLOR}Files created: {', '.join(created_files)}{RESET_COLOR}")
                    break

                if parse_error:
                    print(f"  {ERROR_COLOR}⚠️ Parse error: {parse_error}{RESET_COLOR}")
                    if "missing closing parenthesis" in parse_error or "Incomplete tool call" in parse_error:
                        guidance = "ERROR: File content too long to parse. Split into smaller files (under 80 lines each) or simplify the code."
                    else:
                        guidance = f"ERROR: {parse_error}"
                    conversation.append({"role": "assistant", "content": response})
                    conversation.append({"role": "user", "content": guidance})
                    continue

                print(f"  {ERROR_COLOR}⚠️ No tool call in response{RESET_COLOR}")
                print(f"    Preview: {response[:150]}...")

                if consecutive_no_tool >= 2:
                    nudge = "STOP EXPLAINING. You must call a tool NOW. Example: tool: write_file({\"path\": \"file.py\", \"content\": \"code\"})"
                    conversation.append({"role": "assistant", "content": response})
                    conversation.append({"role": "user", "content": nudge})
                    consecutive_no_tool = 0
                else:
                    conversation.append({"role": "assistant", "content": response})
                    conversation.append({"role": "user", "content": "Call the tool now. Do not explain."})
                continue

            consecutive_no_tool = 0

            name, args = tool_invocations[0]
            action_sig = get_action_signature(name, args)
            action_history.append(action_sig)

            print(f"  Calling: {name}")

            loop_msg = detect_loop(action_history, error_history)
            if loop_msg:
                print(f"  {ERROR_COLOR}⚠️ Loop detected{RESET_COLOR}")
                conversation.append({"role": "assistant", "content": response})
                conversation.append({"role": "user", "content": loop_msg})
                action_history.clear()
                error_history.clear()
                continue

            # Request approval for risky operations
            approved, feedback = request_approval(name, args)
            if not approved:
                print(f"  {ERROR_COLOR}✗ Action rejected{RESET_COLOR}")
                conversation.append({"role": "assistant", "content": response})
                conversation.append({"role": "user", "content": feedback})
                continue

            conversation.append({"role": "assistant", "content": response})

            result = execute_tool(name, args)
            hint = show_tool_result(name, result)

            if result.get("error"):
                error_history.append(str(result.get("error", "")))
                if len(error_history) > 5:
                    error_history.pop(0)

            if name == "write_file" and result.get("action") == "written":
                created_files.add(args.get("path", ""))

            if name == "run_command":
                returncode = result.get("returncode", 0)
                stderr = result.get("stderr", "").strip()
                stdout = result.get("stdout", "").strip()
                
                if returncode != 0:
                    if stderr:
                        error_history.append(stderr)
                        if len(error_history) > 5:
                            error_history.pop(0)
                    result_str = f"ERROR:\n{stderr}\n\nFull result: {json.dumps(result)}"
                
                elif not stdout and not stderr:
                    result_str = f"{json.dumps(result)}\n\nSUCCESS: Program ran successfully (returncode=0). Interactive programs like games don't produce console output. Task complete."
                
                else:
                    result_str = json.dumps(result)
            else:
                result_str = json.dumps(result)
                if len(result_str) > 3000:
                    result_str = result_str[:3000] + "...(truncated)"

            if hint:
                conversation.append({"role": "user", "content": f"Result: {result_str}\n\nHINT: {hint}"})
            else:
                conversation.append({"role": "user", "content": f"Result: {result_str}"})

        if step >= MAX_STEPS:
            print(f"\n{ERROR_COLOR}⚠️ Hit {MAX_STEPS} step limit{RESET_COLOR}")

        if len(conversation) > 40:
            summary = f"[Previous work: Created files: {', '.join(created_files) if created_files else 'none yet'}]"
            conversation = [conversation[0], {"role": "user", "content": summary}] + conversation[-25:]


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Local coding agent with human-in-the-loop approval",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Modes:
  Default (manual):  Requires approval for file changes and commands
  Auto (--auto):     Executes all operations automatically

During a session, type 'a' or 'auto' at any approval prompt to switch to auto mode.
        """
    )
    parser.add_argument(
        "--auto", "-a",
        action="store_true",
        help="Run in auto mode (no approval prompts for actions)"
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    run_coding_agent_loop(auto_mode=args.auto)
