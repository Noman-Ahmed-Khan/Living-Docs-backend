"""Container startup helper for Docker Compose."""

import os
import subprocess
import sys
import time

from sqlalchemy import create_engine, text


def wait_for_database() -> None:
    """Block until the configured database accepts connections."""
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print("DATABASE_URL is not set; skipping database readiness check.", flush=True)
        return

    timeout_seconds = int(os.environ.get("DB_WAIT_TIMEOUT", "60"))
    deadline = time.time() + timeout_seconds
    last_error = None

    print("Waiting for database...", flush=True)
    while time.time() < deadline:
        engine = None
        try:
            engine = create_engine(database_url, pool_pre_ping=True)
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            print("Database is ready.", flush=True)
            return
        except Exception as exc:  # pragma: no cover - exercised in container startup
            last_error = exc
            print(f"Database not ready yet: {exc}", flush=True)
            time.sleep(2)
        finally:
            if engine is not None:
                engine.dispose()

    raise RuntimeError(
        f"Database did not become ready within {timeout_seconds} seconds: {last_error}"
    )


def run_migrations() -> None:
    """Apply Alembic migrations before the API starts."""
    print("Running database migrations...", flush=True)
    subprocess.run(["alembic", "upgrade", "head"], check=True)


def build_uvicorn_command() -> list[str]:
    """Construct the Uvicorn command from environment variables."""
    port = os.environ.get("PORT", "8000")
    reload_enabled = os.environ.get("UVICORN_RELOAD", "false").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }

    command = [
        "uvicorn",
        "app.main:app",
        "--host",
        "0.0.0.0",
        "--port",
        port,
    ]
    if reload_enabled:
        command.append("--reload")
    return command


def main() -> None:
    """Prepare the container, then replace the process with Uvicorn."""
    upload_dir = os.environ.get("UPLOAD_DIR", "./uploads")
    os.makedirs(upload_dir, exist_ok=True)

    wait_for_database()
    run_migrations()

    command = build_uvicorn_command()
    print(f"Starting API with: {' '.join(command)}", flush=True)
    os.execvp(command[0], command)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Container startup failed: {exc}", file=sys.stderr, flush=True)
        raise
