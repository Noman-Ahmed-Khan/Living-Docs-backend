#!/usr/bin/env bash
set -euo pipefail

compose() {
    if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
        docker compose "$@"
        return
    fi

    if command -v docker-compose >/dev/null 2>&1; then
        docker-compose "$@"
        return
    fi

    echo "Docker Compose is not available. Install Docker Desktop or docker-compose first." >&2
    exit 1
}

show_help() {
    cat <<'EOF'
Usage: ./docker-helper.sh [command] [service]

Commands:
  up          Build and start containers in detached mode
  down        Stop and remove containers
  build       Build or rebuild services
  logs        Follow container logs (optionally pass a service name)
  migrate     Run database migrations in the backend container
  shell       Open a POSIX shell in the backend container
  ps          List containers
  config      Render the resolved Compose configuration
  clean       Remove this project's containers, volumes, and unused Docker data
EOF
}

command_name="${1:-help}"
service_name="${2:-}"

case "${command_name}" in
    up)
        compose up -d --build --remove-orphans
        ;;
    down)
        compose down --remove-orphans
        ;;
    build)
        compose build
        ;;
    logs)
        if [[ -n "${service_name}" ]]; then
            compose logs -f "${service_name}"
        else
            compose logs -f
        fi
        ;;
    migrate)
        compose exec backend alembic upgrade head
        ;;
    shell)
        compose exec backend sh
        ;;
    ps)
        compose ps
        ;;
    config)
        compose config
        ;;
    clean)
        compose down -v --remove-orphans
        docker system prune -f
        ;;
    *)
        show_help
        exit 1
        ;;
esac
