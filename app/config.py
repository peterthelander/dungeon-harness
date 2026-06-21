import os
from dataclasses import dataclass


@dataclass(frozen=True)
class RuntimeConfig:
    environment: str
    flask_secret_key: str
    max_upload_bytes: int
    max_remote_download_bytes: int
    remote_download_timeout_seconds: int
    session_ttl_seconds: int
    max_sessions: int

    @property
    def is_production(self) -> bool:
        return self.environment.lower() in {"prod", "production"}


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"Environment variable {name} must be an integer.") from exc
    if value <= 0:
        raise ValueError(f"Environment variable {name} must be positive.")
    return value


def load_runtime_config() -> RuntimeConfig:
    environment = os.environ.get("APP_ENV", "development")
    secret_key = os.environ.get("FLASK_SECRET_KEY")
    if not secret_key:
        if environment.lower() in {"prod", "production"}:
            raise RuntimeError("FLASK_SECRET_KEY must be set in production.")
        secret_key = os.urandom(32).hex()

    return RuntimeConfig(
        environment=environment,
        flask_secret_key=secret_key,
        max_upload_bytes=_env_int("MAX_UPLOAD_BYTES", 20 * 1024 * 1024),
        max_remote_download_bytes=_env_int("MAX_REMOTE_DOWNLOAD_BYTES", 20 * 1024 * 1024),
        remote_download_timeout_seconds=_env_int("REMOTE_DOWNLOAD_TIMEOUT_SECONDS", 20),
        session_ttl_seconds=_env_int("SESSION_TTL_SECONDS", 60 * 60),
        max_sessions=_env_int("MAX_SESSIONS", 500),
    )
