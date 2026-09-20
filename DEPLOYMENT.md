# 🚀 Wealth OS Deployment Guide (Streamlit Cloud)

Follow these steps to deploy your **Wealth OS | Quant Terminal** to the web.

## 1. Prepare your GitHub Repository
Ensure your repository is up-to-date and contains the following files:
- `streamlit_app.py` (Main entry point)
- `requirements.txt` (Dependencies)
- `.streamlit/config.toml` (Theme settings)
- `core/`, `finance/`, `data/` (Project packages)

## 2. Deploy on Streamlit Cloud
1. Go to [share.streamlit.io](https://share.streamlit.io/).
2. Click **"New app"**.
3. Select your GitHub repository, the `main` branch, and set the file path to `streamlit_app.py`.
4. Click **"Deploy!"**.

## 3. Configure Secrets (CRITICAL)
Once the app is deploying, go to **Settings > Secrets** in the Streamlit dashboard and paste your `.env` variables in TOML format:

```toml
SUPABASE_URL = "your_supabase_url"
SUPABASE_SERVICE_ROLE_KEY = "your_supabase_key"

# AI Provider Configuration
MODEL_PROVIDER = "gemini" # recommended for cloud
GEMINI_API_KEY = "your_gemini_api_key"
OPENAI_API_KEY = "your_openai_api_key"

# If using a remote Ollama instance
OLLAMA_BASE_URL = "https://your-ollama-endpoint.com/v1"
OLLAMA_MODEL = "llama3.2"
```

## 4. Local vs Cloud Model Selection
- **Ollama**: Only works if your Ollama instance is accessible via a public URL. Localhost URLs will **not** work on Streamlit Cloud.
- **Gemini/OpenAI**: Recommended for the cloud deployment as they are globally reachable.

## 5. Continuous Deployment
Every time you push to your GitHub repository, Streamlit Cloud will automatically rebuild and redeploy your Wealth OS terminal.
