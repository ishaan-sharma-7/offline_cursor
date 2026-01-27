"""Streaming output for real-time LLM response display."""
import ollama
from enum import Enum
from typing import List, Dict
from .display import ASSISTANT_COLOR, RESET_COLOR
from .model_config import MODEL_NAME, MODEL_OPTIONS


class StreamMode(Enum):
    """Streaming display modes."""
    SILENT = "silent"      # No streaming output
    THOUGHTS = "thoughts"  # Stream all output (same as FULL now)
    FULL = "full"          # Stream everything


def execute_llm_streaming(
    conversation: List[Dict[str, str]],
    mode: StreamMode = StreamMode.SILENT
) -> str:
    """
    Execute LLM call with optional streaming output.

    Args:
        conversation: Conversation history
        mode: Streaming mode (SILENT, THOUGHTS, or FULL)

    Returns:
        Complete LLM response text
    """
    if mode == StreamMode.SILENT:
        # Non-streaming mode
        response = ollama.chat(
            model=MODEL_NAME,
            messages=conversation,
            options=MODEL_OPTIONS
        )
        return response['message']['content']

    # Streaming modes (FULL and THOUGHTS are now identical)
    full_response = []

    print(f"\n{ASSISTANT_COLOR}🧠 Thinking...{RESET_COLOR}", flush=True)

    try:
        for chunk in ollama.chat(
            model=MODEL_NAME,
            messages=conversation,
            options=MODEL_OPTIONS,
            stream=True
        ):
            content = chunk['message']['content']
            full_response.append(content)
            print(content, end='', flush=True)

        print()  # Newline after streaming

    except KeyboardInterrupt:
        print(f"\n{RESET_COLOR}[Interrupted]")
        return ''.join(full_response)

    return ''.join(full_response)
