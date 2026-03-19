# Security

Security considerations for Email Agent.

## Never Send Policy

Email Agent **never sends emails automatically**.

### Enforcement

1. **Code design**: Only `users.drafts.create()` API used
2. **Pre-commit pygrep hook**: Prevents commits containing `.send(` in src/
3. **CI ruff check**: Catches any bypassed commits
4. **Tests**: Verify no send calls exist

### Why No Auto-Send?

- AI can make mistakes
- User should review all responses
- Liability protection
- Trust without verification

## Credentials

### Store Securely

Credentials stored in `credentials/` folder:
- `credentials.json` - OAuth client secrets
- `token.json` - OAuth access tokens

### Never Commit

Never commit credentials or tokens to git:
- `credentials/` - OAuth secrets and tokens
- `config.yaml` - May contain sensitive patterns

### Token Security

- Tokens auto-managed by Google auth library
- Stored in `credentials/token.json` (not encrypted at rest by this app)
- User can revoke at any time via Google account

## Local Processing

### All Data Stays Local

- LLM runs on your machine (Ollama)
- Email content never sent to external AI services
- No cloud dependencies for AI processing

### Network Access

Required network access:
- `localhost:11434` - Ollama API
- `oauth2.googleapis.com` - Token refresh
- `gmail.googleapis.com` - Email access

## Config Security

### Sensitive Data

`config.yaml` may contain:
- Email addresses (not secrets)
- Domain patterns (@company.com)

No passwords or API keys stored.

### File Permissions

```bash
# Linux/macOS
chmod 600 config.yaml credentials/

# Windows
# Ensure files not shared publicly
```

## OAuth Scopes

Only minimum necessary scopes:
- `gmail.readonly` - Read emails only
- `gmail.labels` - Manage labels only
- `gmail.compose` - Create drafts only

No access to:
- Send emails
- Delete emails
- Modify emails

## Best Practices

1. **Review drafts** before sending
2. **Revoke access** when not using agent
3. **Keep Ollama local** - don't expose to network
4. **Update regularly** - keep dependencies current
5. **Monitor logs** - check for unusual activity
