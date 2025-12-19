# API Key Setup Guide

## Quick Setup Options

### Option 1: Environment Variable (Recommended)

**Windows (PowerShell):**
```powershell
$env:OPENROUTER_API_KEY="your-api-key-here"
streamlit run app.py
```

**Windows (Command Prompt):**
```cmd
set OPENROUTER_API_KEY=your-api-key-here
streamlit run app.py
```

**Linux/Mac:**
```bash
export OPENROUTER_API_KEY="your-api-key-here"
streamlit run app.py
```

### Option 2: Streamlit Secrets File

1. Create a folder named `.streamlit` in your project directory (`C:\sb 2\.streamlit\`)
2. Create a file named `secrets.toml` inside that folder
3. Add your API key:

```toml
[openrouter]
api_key = "your-api-key-here"
```

**File structure:**
```
C:\sb 2\
├── app.py
├── .streamlit\
│   └── secrets.toml
└── ...
```

### Option 3: Temporary (Testing Only)

If you just need to test quickly, you can temporarily modify line 49 in `app.py`:

```python
OPENROUTER_API_KEY = "your-api-key-here"  # TEMPORARY - Remove before committing!
```

**Warning:** Never commit API keys to version control!

## Getting Your OpenRouter API Key

1. Go to https://openrouter.ai/
2. Sign up or log in
3. Navigate to your API keys section
4. Create a new API key
5. Copy the key and use it in one of the methods above

## Verification

After setting up, run the app:
```bash
streamlit run app.py
```

If the API key is correctly configured, the app will start without errors. If not, you'll see a helpful error message with these instructions.





