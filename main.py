
import os
from pathlib import Path

import yaml
from dotenv import dotenv_values
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

BASE_DIR = Path(__file__).resolve().parent

DEFAULTS = {
    "port": 8000,
    "workers": 1,
    "debug": False,
    "log_level": "info",
    "api_key": "default-secret-000",
}

ALLOWED_KEYS = set(DEFAULTS)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def normalize_config(layer):
    result = {}

    for key, value in layer.items():
        if value is None:
            continue

        key = str(key).lower()

        if key.startswith("app_"):
            key = key[4:]

        if key == "num_workers":
            key = "workers"

        if key in ALLOWED_KEYS:
            result[key] = value

    return result


def coerce_value(key, value):
    if key in ("port", "workers"):
        return int(value)

    if key == "debug":
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in (
            "true", "1", "yes", "on"
        )

    return str(value)


@app.get("/effective-config")
def effective_config(
    set_values: list[str] = Query(default=[], alias="set")
):
    config = DEFAULTS.copy()

    # Layer 2: environment-specific YAML
    environment = os.environ.get("APP_ENV", "development")
    yaml_path = BASE_DIR / f"config.{environment}.yaml"

    if yaml_path.exists():
        with open(yaml_path, "r", encoding="utf-8") as file:
            yaml_config = yaml.safe_load(file) or {}
        config.update(normalize_config(yaml_config))

    # Layer 3: .env file
    env_path = BASE_DIR / ".env"
    env_file = dotenv_values(env_path) if env_path.exists() else {}
    config.update(normalize_config(env_file))

    # Layer 4: OS environment variables
    os_config = {
        key: value
        for key, value in os.environ.items()
        if key.startswith("APP_")
    }
    config.update(normalize_config(os_config))

    # Layer 5: CLI query overrides
    for entry in set_values:
        if "=" not in entry:
            continue

        key, value = entry.split("=", 1)
        key = key.strip().lower()

        if key.startswith("app_"):
            key = key[4:]

        if key == "num_workers":
            key = "workers"

        if key in ALLOWED_KEYS:
            config[key] = value

    result = {
        key: coerce_value(key, value)
        for key, value in config.items()
    }

    result["api_key"] = "****"

    return result