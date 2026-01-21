"""Parsing utilities for extracting tool invocations from LLM responses."""
import ast
import json
import re
from typing import Any, Dict, List, Tuple


def normalize_multiline_strings(text: str) -> str:
    """
    Replace literal newlines inside string literals with \\n.
    This fixes the most common parse failure.
    """
    result = []
    in_string = False
    string_char = None
    i = 0

    while i < len(text):
        char = text[i]

        if char == '\\' and i + 1 < len(text):
            result.append(char)
            result.append(text[i + 1])
            i += 2
            continue

        if char in ('"', "'"):
            if not in_string:
                in_string = True
                string_char = char
            elif char == string_char:
                in_string = False
                string_char = None
            result.append(char)
        elif char == '\n':
            if in_string:
                result.append('\\n')
            else:
                result.append(char)
        else:
            result.append(char)
        i += 1

    return ''.join(result)


def extract_tool_invocations(text: str, tool_registry: Dict) -> Tuple[List[Tuple[str, Dict[str, Any]]], str]:
    """
    Parse tool calls from LLM response.

    Returns:
        (invocations, error_message) - invocations is list of (tool_name, args) tuples,
        error_message is empty string if successful, otherwise describes the problem.
    """
    clean_text = text.replace("```python", "").replace("```json", "").replace("```", "").strip()
    clean_text = normalize_multiline_strings(clean_text)

    match = re.search(r"tool:\s*(\w+)\s*\(", clean_text)
    if not match:
        match = re.search(r"^(\w+)\s*\(\s*\{", clean_text, re.MULTILINE)
        if not match:
            for tool_name in tool_registry:
                if tool_name in text.lower():
                    return [], f"You mentioned '{tool_name}' but didn't call it. Call it now: tool: {tool_name}({{...}})"
            return [], ""

    tool_name = match.group(1)
    if tool_name not in tool_registry:
        return [], f"Unknown tool: {tool_name}"

    start_idx = match.end() - 1

    # Find matching closing parenthesis
    balance = 0
    in_string = False
    string_char = None
    i = start_idx
    end_idx = -1

    while i < len(clean_text):
        char = clean_text[i]

        # Handle escape sequences - but only when inside a string
        if in_string and char == '\\' and i + 1 < len(clean_text):
            i += 2
            continue

        if char in ('"', "'"):
            if not in_string:
                in_string = True
                string_char = char
            elif char == string_char:
                in_string = False
                string_char = None

        if not in_string:
            if char == '(':
                balance += 1
            elif char == ')':
                balance -= 1
                if balance == 0:
                    end_idx = i
                    break

        i += 1

    if end_idx == -1:
        # Debug: show what we're parsing
        snippet = clean_text[max(0, start_idx):min(len(clean_text), start_idx + 200)]
        return [], f"Incomplete tool call for '{tool_name}'. Debug: balance={balance}, in_string={in_string}, snippet={snippet[:100]}"

    args_str = clean_text[start_idx + 1:end_idx]
    dict_start = args_str.find('{')
    dict_end = args_str.rfind('}')

    if dict_start == -1 or dict_end == -1:
        return [], f"No arguments dict found for '{tool_name}'. Use: tool: {tool_name}({{\"key\": \"value\"}})"

    json_str = args_str[dict_start:dict_end + 1]

    # Try to parse the arguments
    args = None
    parse_error = None

    try:
        args = ast.literal_eval(json_str)
    except Exception as e:
        parse_error = str(e)

    if args is None:
        try:
            args = json.loads(json_str)
            parse_error = None
        except Exception as e:
            if parse_error is None:
                parse_error = str(e)

    if args is None:
        try:
            fixed = json_str.replace("'", '"')
            args = json.loads(fixed)
            parse_error = None
        except:
            pass

    if args is None:
        return [], f"Could not parse arguments for '{tool_name}': {parse_error}. Use double quotes and \\n for newlines."

    return [(tool_name, args)], ""
