from pydantic import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = 'Panveliq'

settings = Settings()
