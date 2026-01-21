# Offline Cursor - Local AI Coding Agent

A command-line coding agent powered by Ollama and Qwen 2.5 Coder that can read, write, edit files, run commands, and complete coding tasks entirely offline.

## Project Structure

```
offline_cursor/
├── coding_agent.py       # Main agent loop and LLM interaction (215 lines)
├── utils/                # Utilities package (630 lines total)
│   ├── __init__.py       # Package exports (46 lines)
│   ├── tools.py          # File operation tools (233 lines)
│   ├── registry.py       # Tool registry and execution (68 lines)
│   ├── parsing.py        # Tool invocation parsing (147 lines)
│   ├── display.py        # UI and colored output (69 lines)
│   └── loop_detection.py # Prevents repetitive actions (67 lines)
├── requirements.txt      # Python dependencies
└── README.md             # This file
```

**Code Organization:**

- **coding_agent.py** - Core agent logic, system prompt, and main loop
- **utils/** - Organized utilities package:
  - **tools.py** - All file operations (read, write, edit, delete, search, commands)
  - **registry.py** - Tool registry and execution dispatcher
  - **parsing.py** - Extracts tool calls from LLM responses
  - **display.py** - Colored terminal output and user input
  - **loop_detection.py** - Detects and prevents infinite loops
  - **\_\_init\_\_.py** - Clean package interface with exports

## Features

- **File Operations**: Create, read, edit, and delete files
- **Code Editing**: Insert, replace, or delete specific lines in files
- **Command Execution**: Run shell commands with timeout protection
- **File Search**: Search for patterns across files using regex
- **Offline Operation**: Runs completely offline using local LLM via Ollama
- **Loop Detection**: Automatically detects and prevents repetitive actions
- **Interactive CLI**: Multi-line input with simple SUBMIT command

## Prerequisites

- Python 3.11+
- [Ollama](https://ollama.ai/) installed and running
- Qwen 2.5 Coder model (14B version)

## Installation

1. Install Ollama from [https://ollama.ai/](https://ollama.ai/)

2. Start the Ollama service:

```bash
ollama serve
```

(Keep this running in a separate terminal)

3. Pull the Qwen 2.5 Coder model (in a new terminal):

```bash
ollama pull qwen2.5-coder:14b
```

4. Clone this repository:

```bash
git clone <repository-url>
cd offline_cursor
```

5. Create a virtual environment and install dependencies:

```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Usage

Run the coding agent:

```bash
python coding_agent.py
```

The agent will prompt you to enter your request. Type your instructions, then type `SUBMIT` on a new line to send.

Press `Ctrl+C` to exit at any time.

## Available Tools

The agent has access to the following tools:

- `read_file(filename)` - Read complete file contents
- `list_files(path)` - List files and directories
- `write_file(path, content)` - Create or overwrite a file
- `view_file(filename, start_line, end_line)` - View file with line numbers
- `insert_lines(path, line, content)` - Insert lines before specified line
- `replace_lines(path, start, end, content)` - Replace specific line range
- `delete_lines(path, start, end)` - Delete specific line range
- `run_command(command, working_dir)` - Execute shell commands
- `search_in_files(pattern, path, file_pattern)` - Search across files
- `delete(path)` - Delete file or directory

## Configuration

The agent uses the following Ollama parameters (configured in [coding_agent.py](coding_agent.py)):

- Model: `qwen2.5-coder:14b` (edit in `execute_llm_call()` function)
- Temperature: `0.0` (deterministic)
- Max tokens: `4096`
- Context window: `8192`
- Max steps: `50` per request
- Command timeout: `30 seconds` (configured in [utils.py](utils.py))

## How It Works

1. The agent maintains a conversation history with the LLM
2. User requests are sent to the Qwen model via Ollama
3. The model responds with tool calls in a specific format
4. Tools are executed and results are fed back to the model
5. The process continues until the task is complete or max steps (50) is reached
6. Loop detection prevents the agent from repeating failed actions

## Limitations

- Maximum 50 steps per request
- 30-second timeout for shell commands
- Works best with structured coding tasks
- Requires Ollama to be running locally
