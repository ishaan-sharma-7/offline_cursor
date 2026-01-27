"""Model configuration for the coding agent.

Change MODEL_NAME here to use a different Ollama model.
"""

# Model configuration - change this to use a different model
MODEL_NAME = "qwen3-coder:30b"

# Model options
MODEL_OPTIONS = {
    "temperature": 0.0,
    "num_predict": 4096,
    "num_ctx": 8192,
    "stop": ["User:", "\n\nYou (type"],
}
