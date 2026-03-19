# Troubleshooting

Solutions to common problems.

## Installation Issues

### uv command not found

```bash
pip install uv
```

### Python version error

Requires Python 3.13+. Check version:

```bash
python --version
```

Install from [python.org](https://www.python.org/downloads/) if needed.

## Ollama Connection Issues

### "Cannot connect to Ollama"

1. Verify Ollama is running:
   ```bash
   ollama list
   ```

2. Check service:
   ```bash
   # Windows
   curl http://localhost:11434/api/tags

   # Linux/macOS
   curl http://localhost:11434/api/tags
   ```

3. Restart Ollama:
   ```bash
   # Windows: Restart service or run
   ollama serve

   # Linux/macOS
   sudo systemctl restart ollama
   ```

### "Model not found"

```bash
ollama pull llama3.2:1b
```

### Slow LLM responses

- Reduce `max_emails_per_batch` in config
- Use smaller model
- Increase `timeout` in config

## Gmail Authentication Errors

### "Invalid credentials file"

1. Verify `credentials/credentials.json` exists
2. Check JSON is valid (download fresh from Cloud Console)
3. Ensure Gmail API is enabled

### "Token expired or revoked"

```bash
rm credentials/token.json
python -m email_agent setup
```

### "Access denied"

1. Check OAuth consent screen
2. Add your email as test user
3. Re-authorize in browser

## Configuration Errors

### "Config validation failed"

Check `config.yaml` for:
- Missing required fields
- Invalid types
- Values out of range

Run validation:

```bash
python -m email_agent --dry-run --verbose
```

### "Categories must be unique"

Case-insensitive duplicates not allowed:

```yaml
# Bad
categories:
  - "Work"
  - "work"

# Good
categories:
  - "Work"
  - "Personal"
```

## Runtime Issues

### Agent stops after first poll

Run with `--verbose` to see errors:

```bash
python -m email_agent --verbose
```

### Emails not being labeled

1. Check labels exist in Gmail
2. Verify Gmail API scopes
3. Run in verbose mode to see LLM decisions

### No draft replies created

1. Check important_senders in config
2. LLM decides which emails need replies
3. Run verbose to see decisions

## Logging

Logs saved to `email-agent.log`:

```bash
# View recent logs
tail -f email-agent.log

# Search for errors
grep ERROR email-agent.log
```

## Getting Help

1. Run with `--verbose` for detailed output
2. Check logs in `email-agent.log`
3. Search for `ERROR` in logs: `grep ERROR email-agent.log`
