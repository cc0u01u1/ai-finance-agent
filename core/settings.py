import os
from typing import Optional
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.providers.ollama import OllamaProvider
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.models.openai import OpenAIChatModel


class Settings:
    # Model Configuration
    @property
    def MODEL_PROVIDER(self) -> str:
        return os.getenv('MODEL_PROVIDER', 'ollama').lower()

    @property
    def OLLAMA_MODEL(self) -> str:
        return os.getenv('OLLAMA_MODEL', 'llama3.2')

    @property
    def OLLAMA_BASE_URL(self) -> str:
        return os.getenv('OLLAMA_BASE_URL', 'http://localhost:11434/v1')

    @property
    def OLLAMA_API_KEY(self) -> Optional[str]:
        return os.getenv('OLLAMA_API_KEY')

    @property
    def OPENAI_MODEL(self) -> str:
        return os.getenv('OPENAI_MODEL', 'gpt-4o')

    @property
    def GEMINI_MODEL(self) -> str:
        return os.getenv('GEMINI_MODEL', 'gemini-2.0-flash')
    
    # API Keys
    @property
    def GEMINI_API_KEY(self) -> Optional[str]:
        return os.getenv('GEMINI_API_KEY')

    @property
    def OPENAI_API_KEY(self) -> Optional[str]:
        return os.getenv('OPENAI_API_KEY')

    # MLflow Configuration
    @property
    def MLFLOW_TRACKING_URI(self) -> str:
        return os.getenv('MLFLOW_TRACKING_URI', 'sqlite:///mlflow.db')

    @property
    def MLFLOW_EXPERIMENT_NAME(self) -> str:
        return os.getenv('MLFLOW_EXPERIMENT_NAME', 'Personal Finance Assistant')

    def get_model(self, override_provider: str = None):
        """
        Unified model provider selection.
        """
        provider = (override_provider or self.MODEL_PROVIDER).lower()
        
        if provider in ['gemini', 'google']:
            api_key = self.GEMINI_API_KEY or os.getenv('GOOGLE_API_KEY')
            if not api_key:
                # We return a string here to let Pydantic AI try to find it in the env
                # but it's better to be explicit.
                return GoogleModel(self.GEMINI_MODEL)
            return GoogleModel(self.GEMINI_MODEL, api_key=api_key)
            
        elif provider == 'ollama':            
            base_url = self.OLLAMA_BASE_URL
            if 'ollama.com' in base_url.lower() and not base_url.endswith('/v1'):
                base_url = base_url.rstrip('/') + '/v1'
                
            provider_inst = OllamaProvider(
                base_url=base_url,
                api_key=self.OLLAMA_API_KEY
            )
            return OpenAIChatModel(self.OLLAMA_MODEL, provider=provider_inst)
            
        elif provider == 'openai':
            if self.OPENAI_API_KEY:
                # Pydantic AI 1.x: key goes through the provider
                provider_inst = OpenAIProvider(api_key=self.OPENAI_API_KEY)
                return OpenAIChatModel(self.OPENAI_MODEL, provider=provider_inst)
            return f'openai:{self.OPENAI_MODEL}'
            
        else:
            # Default fallback to Gemini
            api_key = self.GEMINI_API_KEY or os.getenv('GOOGLE_API_KEY')
            return GoogleModel(self.GEMINI_MODEL, api_key=api_key)

# Global settings instance
settings = Settings()
