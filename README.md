# Offline Cursor - Local AI Coding Agent

A command-line coding agent powered by Ollama and Qwen 2.5 Coder that can read, write, edit files, run commands, and complete coding tasks entirely offline.

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

2. Pull the Qwen 2.5 Coder model:

```bash
ollama pull qwen2.5-coder:14b
```

3. Clone this repository:

```bash
git clone <repository-url>
cd offline_cursor
```

4. Create a virtual environment and install dependencies:

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

The agent uses the following Ollama parameters (configured in [coding_agent.py:454-459](coding_agent.py#L454-L459)):

- Model: `qwen2.5-coder:14b`
- Temperature: `0.0` (deterministic)
- Max tokens: `4096`
- Context window: `8192`
- Timeout: `30 seconds` for shell commands

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

## License

See LICENSE file for details.
