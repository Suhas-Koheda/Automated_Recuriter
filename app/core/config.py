from pydantic_settings import BaseSettings
from typing import Optional
import os
from pathlib import Path


class Settings(BaseSettings):
    # API Prefix
    API_V1_STR: str = "/api/v1"
    
    # Project information
    PROJECT_NAME: str = "AI Interview Automation"
    
    # Database settings
    DATABASE_URL: str = "sqlite:///./interview_automation.db"
    
    # Gemini API settings
    GEMINI_API_KEY: str = "AIzaSyDm3VI03IMnQXkGz6CNXHD6-eubZy38M0s"
    
    # Zoom API settings
    ZOOM_ACCOUNT_ID: str = "JbgHYsKOS-iv_PwOxkKl4A"
    ZOOM_CLIENT_ID: str = "9XT8h92aTFCP3ICabKkKQ"
    ZOOM_CLIENT_SECRET: str = "Be29nhxYpqxcEaEnJnMaxOthTX7B0YEO"
    ZOOM_REDIRECT_URI: str = "http://localhost:8000/api/v1/zoom/callback"
    
    # Email settings
    EMAIL_SENDER: str = "interviews@example.com"
    EMAIL_PASSWORD: str = "your_email_password"  # In production, use env vars
    EMAIL_HOST: str = "smtp.gmail.com"
    EMAIL_PORT: int = 587
    
    # JWT settings
    SECRET_KEY: str = "supersecretkey"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    
    # Storage paths
    RECORDING_PATH: str = str(Path("recordings").absolute())
    REPORTS_PATH: str = str(Path("reports").absolute())
    
    class Config:
        env_file = ".env"


# Create directories if they don't exist
def create_directories():
    paths = [settings.RECORDING_PATH, settings.REPORTS_PATH]
    for path in paths:
        os.makedirs(path, exist_ok=True)


settings = Settings()