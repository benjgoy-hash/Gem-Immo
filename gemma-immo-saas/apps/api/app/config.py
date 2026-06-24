from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    api_title: str = "Gemma Immo API"
    api_version: str = "0.1.0"
    data_dir: Path = Field(default=Path(__file__).resolve().parent / "data")
    results_filename: str = "resultats.csv"
    fallback_results_filename: str = "resultats.sample.csv"
    prices_filename: str = "prix_immo.csv"

    @property
    def results_path(self) -> Path:
        primary = self.data_dir / self.results_filename
        if primary.exists():
            return primary
        return self.data_dir / self.fallback_results_filename

    @property
    def prices_path(self) -> Path:
        return self.data_dir / self.prices_filename


@lru_cache
def get_settings() -> Settings:
    return Settings()

