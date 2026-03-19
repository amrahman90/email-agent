# Ollama Setup

Installing and configuring Ollama for Email Agent.

## Installation

### Windows

1. Download from [ollama.com/download](https://ollama.com/download)
2. Run installer
3. Ollama starts automatically in background

### WSL2 / Linux

```bash
curl -fsSL https://ollama.com/install.sh | sh
```

### macOS

```bash
brew install ollama
```

## Pull the Model

```bash
ollama pull llama3.2:1b
```

Model size: ~1.3GB download.

## Verify Installation

### Check Ollama is Running

```bash
ollama list
```

Expected output:
```
NAME                    ID           SIZE      MODIFIED
llama3.2:1b            a12abc...    900MB     2024-01-01
```

### Test API Connection

```bash
curl http://localhost:11434/api/tags
```

Expected JSON response with model list.

## Configuration

Default settings in `config.yaml`:

```yaml
ollama:
  base_url: "http://localhost:11434"
  model: "llama3.2:1b"
  timeout: 120
```

### Changing Model

Edit `config.yaml`:

```yaml
ollama:
  model: "llama3.2:1b"  # Change to other model
```

### Other Tested Models (Compatibility Reference)

For future compatibility testing:

| Model | Size | Notes |
|-------|------|-------|
| `qwen2.5:0.5b` | ~400MB | Smaller, faster, lower quality |
| `qwen2.5:1.5b` | ~1GB | Balanced option |
| `llama3.2:1b` | ~1.3GB | Default model |
| `llama3.2:3b` | ~2GB | Higher quality, slower |

## Health Check

Email Agent runs health check at startup:

1. Calls `GET /api/tags`
2. Verifies configured model exists
3. Offers to pull model if missing
4. Exits with error if Ollama unreachable

## Troubleshooting

### Ollama not starting

```bash
# Windows: Start manually
ollama serve

# Check status
ollama list
```

### Model not found

```bash
ollama pull llama3.2:1b
```

### Connection refused

Ensure Ollama is running:
```bash
# Linux/macOS
ps aux | grep ollama

# Windows Task Manager
```

### Slow responses

- Reduce batch size in config
- Use smaller model
- Close other applications
