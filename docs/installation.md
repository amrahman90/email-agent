# Installation

Detailed installation instructions for all components.

## Python Environment

### 1. Install Python 3.13+

Download from [python.org](https://www.python.org/downloads/) or use pyenv:

```bash
pyenv install 3.13
pyenv local 3.13
```

### 2. Install uv

```bash
pip install uv
```

### 3. Create Virtual Environment

```bash
cd email-agent
uv venv
uv sync
```

## Ollama Setup

### 1. Install Ollama

**Windows:**
Download from [ollama.com/download](https://ollama.com/download)

**WSL2/Linux:**
```bash
curl -fsSL https://ollama.com/install.sh | sh
```

### 2. Pull the Model

```bash
ollama pull llama3.2:1b
```

### 3. Verify Ollama is Running

```bash
ollama list
curl http://localhost:11434/api/tags
```

## Gmail API Setup

### 1. Create Google Cloud Project

1. Go to [console.cloud.google.com](https://console.cloud.google.com)
2. Create new project
3. Enable Gmail API

### 2. Configure OAuth Consent

1. Go to **APIs & Services > OAuth consent screen**
2. Choose **External** user type
3. Fill in app name and email
4. Add scopes:
   - `https://www.googleapis.com/auth/gmail.readonly`
   - `https://www.googleapis.com/auth/gmail.labels`
   - `https://www.googleapis.com/auth/gmail.compose`

### 3. Create OAuth Credentials

1. Go to **APIs & Services > Credentials**
2. Create **OAuth 2.0 Client ID**
3. Choose **Desktop app** type
4. Download JSON as `credentials/credentials.json`

## First Run Setup

```bash
python -m email_agent setup
```

This interactive wizard will:
1. Copy credentials to correct location
2. Open browser for OAuth authorization
3. Create initial `config.yaml`
4. Verify Ollama connection
5. Create Gmail labels from config

## Verification

Test that everything works:

```bash
# Dry run to verify setup
python -m email_agent --once --dry-run --verbose
```

Expected output shows emails being processed without actual changes.

## Troubleshooting

- [Ollama not responding](troubleshooting.md#ollama-connection-issues)
- [Gmail auth failures](troubleshooting.md#gmail-authentication-errors)
- [Config validation errors](troubleshooting.md#configuration-errors)
