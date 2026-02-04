# Model Configuration Guide

## CLI Commands

Run the agent with different flags:

```bash
# Default (manual approval mode, no streaming)
python coding_agent.py

# Auto mode - no approval prompts
python coding_agent.py --auto
python coding_agent.py -a

# Stream LLM output (see thinking in real-time)
python coding_agent.py --stream thoughts
python coding_agent.py -s full

# Combine flags
python coding_agent.py --auto --stream thoughts
python coding_agent.py -a -s full

# Allow dangerous operations (use with caution)
python coding_agent.py --override-forbidden
```

### Available Flags

| Flag | Short | Values | Description |
|------|-------|--------|-------------|
| `--auto` | `-a` | - | Run without approval prompts |
| `--stream` | `-s` | `silent`, `thoughts`, `full` | Control LLM output streaming |
| `--override-forbidden` | - | - | Allow dangerous operations with confirmation |

### Stream Modes

- **silent** (default): No streaming, just final output
- **thoughts**: Stream LLM thinking in real-time
- **full**: Stream everything (same as thoughts)

---

## Quick Start: Change the Model in ONE Place

To use a different Ollama model, edit **only this file**:

**[utils/model_config.py](utils/model_config.py)**

```python
# Model configuration - change this to use a different model
MODEL_NAME = "qwen3-coder:30b"

# Model options
MODEL_OPTIONS = {
    "temperature": 0.0,
    "num_predict": 4096,
    "num_ctx": 8192,
    "stop": ["User:", "\n\nYou (type"],
}
```

## How to Change Models

### Option 1: Change Model Name Only

Edit line 7 in `utils/model_config.py`:

```python
MODEL_NAME = "your-model-name-here"
```

**Examples**:
- `MODEL_NAME = "qwen3-coder:30b"`
- `MODEL_NAME = "qwen2.5-coder:14b"`
- `MODEL_NAME = "codellama:34b"`
- `MODEL_NAME = "deepseek-coder:33b"`

### Option 2: Change Model Options

Edit the `MODEL_OPTIONS` dictionary:

```python
MODEL_OPTIONS = {
    "temperature": 0.0,        # Randomness (0.0 = deterministic)
    "num_predict": 4096,       # Max tokens to generate
    "num_ctx": 8192,           # Context window size
    "stop": ["User:", "\n\nYou (type"],  # Stop sequences
}
```

**Common adjustments**:
- **Increase context**: `"num_ctx": 16384` (for larger models)
- **Add creativity**: `"temperature": 0.2` (0.0 = deterministic, 1.0 = creative)
- **Longer responses**: `"num_predict": 8192`

## Where This Config Is Used

The centralized config is automatically used in:

1. **[utils/streaming.py](utils/streaming.py)** (lines 79-84, 99-104)
   - Streaming and non-streaming LLM calls

2. **[coding_agent.py](coding_agent.py)** (lines 113-116)
   - Legacy execute_llm_call function (not currently used)

## Verification

After changing the model, verify syntax:

```bash
python3 -m py_compile utils/model_config.py
```

Then run the agent:

```bash
python3 coding_agent.py
```

## Model Recommendations

### For Speed
- `qwen2.5-coder:7b` - Fastest, good for simple tasks
- `qwen2.5-coder:14b` - Balanced speed/quality

### For Quality
- `qwen3-coder:30b` - Best quality (current default)
- `deepseek-coder:33b` - Excellent for complex tasks

### For Large Context
- `qwen2.5-coder:32k` - Extended context window
- Adjust: `"num_ctx": 32768`

## Troubleshooting

### Model Not Found
```
Error: model 'model-name' not found
```

**Solution**: Pull the model first:
```bash
ollama pull model-name
```

### Out of Memory
```
Error: failed to allocate memory
```

**Solution**: Use a smaller model or reduce context:
```python
"num_ctx": 4096  # Reduce from 8192
```

### Responses Cut Off
```
Agent's responses are incomplete
```

**Solution**: Increase generation limit:
```python
"num_predict": 8192  # Increase from 4096
```

---

**That's it!** Change the model in `utils/model_config.py` and you're done.
