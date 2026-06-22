import os
from pathlib import Path
from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

# Dynamically locate the root directory and load the environment variables
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(dotenv_path=BASE_DIR / ".env")


class Settings(BaseSettings):
    """
    Type-safe application settings managed via Pydantic.
    Ensures all vital third-party API configurations are loaded before runtime.
    """
    # API Keys
    GEMINI_API_KEY: str = ""
    TAVILY_API_KEY: str = ""

    # Graph Database
    NEO4J_URI: str
    NEO4J_USERNAME: str = "neo4j"
    NEO4J_PASSWORD: str

    # Global Settings
    ENV: str = "development"
    LOG_LEVEL: str = "INFO"

    model_config = SettingsConfigDict(
        extra="ignore"  # Softly ignore extra parameters in the .env file
    )


# Instantiate a single immutable configuration instance for global access
settings = Settings()


def execute_with_retry(func, *args, **kwargs):
    """
    Executes a Gemini API call with exponential backoff and jitter
    to handle RPM (Requests Per Minute) rate limits.
    """
    import time
    import random
    
    max_retries = 4
    base_delay = 3.0
    
    for attempt in range(max_retries):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            err_msg = str(e).upper()
            is_rate_limit = "429" in err_msg or "RESOURCE_EXHAUSTED" in err_msg or "503" in err_msg or "UNAVAILABLE" in err_msg
            
            if is_rate_limit:
                if attempt == max_retries - 1:
                    print(f"❌ [Retry Error] Max retries reached ({max_retries}/{max_retries}). Raising error.")
                    raise e
                
                # Exponential backoff with jitter
                sleep_time = (base_delay * (2 ** attempt)) + random.uniform(0.5, 1.5)
                print(f"⏳ [Rate Limit / Busy] Attempt {attempt + 1} failed. Retrying in {sleep_time:.2f} seconds...")
                time.sleep(sleep_time)
                continue
            raise e


if __name__ == "__main__":
    print("✅ Configuration loaded successfully.")
    print(f"Targeting Environment: {settings.ENV}")
    print(f"Neo4j URI Domain: {settings.NEO4J_URI.split('://')[-1]}")