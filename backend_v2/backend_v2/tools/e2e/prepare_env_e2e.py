"""Create a local .env.e2e file without copying unnecessary secrets."""

from __future__ import annotations

import argparse
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ENV = ROOT / ".env"
DEFAULT_EXAMPLE = ROOT / ".env.e2e.example"
DEFAULT_TARGET = ROOT / ".env.e2e"

AUTO_COPY_KEYS = {
    "ADMIN_EMAIL",
    "ADMIN_PASSWORD",
    "RECOGNITION_WEBHOOK_SECRET",
    "RECOGNITION_API_TOKEN",
    "FRONTEND_URL",
}
FORCED_DEFAULTS = {
    "BACKEND_URL": "http://localhost:8000",
    "RECOGNITION_SERVICE_URL": "http://localhost:8001",
    "FRONTEND_URL": "http://localhost:5173",
}
NEVER_COPY_KEYS = {
    "DATABASE_URL",
    "SECRET_KEY",
    "CLOUDINARY_API_SECRET",
    "CLOUDINARY_API_KEY",
    "CLOUDINARY_CLOUD_NAME",
    "WHATSAPP_API_TOKEN",
    "ADMIN_PASSWORD_HASH",
}


def parse_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key:
            continue
        values[key] = value.strip().strip('"').strip("'")
    return values


def mask(value: str) -> str:
    if not value:
        return "(empty)"
    if len(value) <= 4:
        return "****"
    return f"{value[:2]}***{value[-2:]}"


def render_env(example_path: Path, source_values: dict[str, str]) -> tuple[str, list[str]]:
    copied: list[str] = []
    output: list[str] = []

    for raw_line in example_path.read_text(encoding="utf-8").splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#") or "=" not in raw_line:
            output.append(raw_line)
            continue

        key, current = raw_line.split("=", 1)
        key = key.strip()
        value = current.strip()

        if key in FORCED_DEFAULTS:
            value = FORCED_DEFAULTS[key]
        elif key in AUTO_COPY_KEYS and key not in NEVER_COPY_KEYS:
            candidate = source_values.get(key, "").strip()
            if candidate:
                value = candidate
                copied.append(key)

        output.append(f"{key}={value}")

    return "\n".join(output).rstrip() + "\n", copied


def confirm_overwrite(target: Path, force: bool) -> bool:
    if not target.exists() or force:
        return True

    try:
        answer = input(f"{target.name} ja existe. Sobrescrever? [s/N] ").strip().lower()
    except EOFError:
        print(f"{target.name} ja existe; nada foi alterado.")
        return False
    if answer in {"s", "sim", "y", "yes"}:
        return True

    print(f"{target.name} preservado; nada foi alterado.")
    return False


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare a local .env.e2e from .env.e2e.example.")
    parser.add_argument("--force", action="store_true", help="Overwrite .env.e2e without prompting.")
    parser.add_argument("--env-file", default=str(DEFAULT_TARGET), help="Target .env.e2e path.")
    parser.add_argument("--example-file", default=str(DEFAULT_EXAMPLE), help="Template .env.e2e.example path.")
    parser.add_argument("--source-env", default=str(DEFAULT_ENV), help="Local backend .env source path.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    target = Path(args.env_file)
    example = Path(args.example_file)
    source_env = Path(args.source_env)

    if not example.exists():
        print(f"Arquivo de exemplo nao encontrado: {example}")
        return 1

    if not confirm_overwrite(target, args.force):
        return 0

    source_values = parse_env(source_env)
    rendered, copied = render_env(example, source_values)
    target.write_text(rendered, encoding="utf-8")

    print(f"{target.name} gerado em {target}")
    if copied:
        masked = ", ".join(f"{key}={mask(source_values.get(key, ''))}" for key in copied)
        print(f"Valores preenchidos a partir de {source_env.name}: {masked}")
    else:
        print("Nenhum valor sensivel foi copiado automaticamente.")
    print("Revise TEST_SCHOOL_EMAIL e TEST_SCHOOL_PASSWORD manualmente antes do E2E real.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
