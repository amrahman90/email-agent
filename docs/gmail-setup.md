# Gmail Setup

Setting up Gmail API access for Email Agent.

## Prerequisites

- Google account
- Access to [Google Cloud Console](https://console.cloud.google.com)

## Step 1: Create Google Cloud Project

1. Go to [console.cloud.google.com](https://console.cloud.google.com)
2. Click **Select a project** > **New Project**
3. Name: `email-agent` (or any name)
4. Click **Create**

## Step 2: Enable Gmail API

1. In Cloud Console, go to **APIs & Services > Library**
2. Search for "Gmail API"
3. Click **Gmail API** > **Enable**

## Step 3: Configure OAuth Consent

1. Go to **APIs & Services > OAuth consent screen**
2. Choose **External** > **Create**
3. Fill in:
   - App name: `Email Agent`
   - User support email: Your email
   - Developer contact: Your email
4. Click **Save and Continue**
5. On Scopes page, click **Add or Remove Scopes**
6. Select:
   - `../auth/gmail.readonly` - Read emails
   - `../auth/gmail.labels` - Manage labels
   - `../auth/gmail.compose` - Create drafts
7. Click **Update** > **Save and Continue**
8. Add test users (your own email) > **Save and Continue**

## Step 4: Create Credentials

1. Go to **APIs & Services > Credentials**
2. Click **+ Create Credentials** > **OAuth client ID**
3. Application type: **Desktop app**
4. Name: `Email Agent Desktop`
5. Click **Create**
6. Click **Download JSON**
7. Save as `credentials/credentials.json` in project folder

## Step 5: First Run Authorization

```bash
python -m email_agent setup
```

1. Opens browser for Google sign-in
2. Grants permissions to Email Agent
3. Token saved to `credentials/token.json`

## Required OAuth Scopes

| Scope | Purpose |
|-------|---------|
| `gmail.readonly` | Read email metadata and content |
| `gmail.labels` | Create and apply labels |
| `gmail.compose` | Create draft replies |

## Token Refresh

Tokens auto-refresh. If revoked:

```bash
rm credentials/token.json
python -m email_agent setup
```

## Security Notes

- Credentials never leave your machine
- All email processing is local
- Tokens stored in `credentials/token.json`
- Never commit credentials to git
