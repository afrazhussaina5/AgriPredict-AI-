# AgriPredict AI — infrastructure for Specific (https://docs.specific.dev)
#
# This one file defines how the project builds, runs and connects to its
# dependencies, both locally (`specific dev`) and in production
# (`specific deploy`). Specific is infrastructure-as-code: values such as
# postgres.main.url resolve to a local database during development and to a
# managed one per deployed environment.
#
# NOTE: written on a machine where the Specific CLI could not be installed
# (native Windows without WSL), so it has NOT been validated by
# `specific check` yet. Run `specific check` after installing the CLI.

# Python build. Specific installs dependencies from requirements.txt /
# pyproject.toml automatically; no build command is needed because uvicorn
# serves the app directly.
build "api" {
  base = "python"
}

# One public service: this FastAPI app serves both the JSON API (/api/*) and
# the single-page frontend shell (index.html + static/) from the same process,
# so a single service is enough.
service "api" {
  build   = build.api
  command = "uvicorn backend.main:app --host 0.0.0.0 --port $PORT"

  endpoint {
    public = true

    # The app always serves "/" (the SPA shell), so use it as a cheap probe.
    health_check {
      path = "/"
    }
  }

  env = {
    PORT        = port
    ENVIRONMENT = "production"

    # Injected automatically: local Postgres during `specific dev`, a managed
    # PostgreSQL (Neon) database per deployed environment.
    DATABASE_URL = postgres.main.url

    # Government Mandi (data.gov.in) price feed.
    MARKET_API_URL = config.market_api_url
    MARKET_API_KEY = secret.market_api_key
  }

  # In development Specific does not activate a virtualenv, so point at the
  # interpreter inside it. Create it once from the project root (in WSL/Linux):
  #   python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
  dev {
    command = ".venv/bin/uvicorn backend.main:app --host 0.0.0.0 --port $PORT --reload"
  }
}

# Managed PostgreSQL, with a local instance during `specific dev`.
postgres "main" {}

# Non-sensitive: the data.gov.in resource endpoint for daily mandi prices.
# Override per environment from the dashboard, or locally in specific.local.
config "market_api_url" {
  default = "https://api.data.gov.in/resource/9ef84268-d588-465a-a308-a864a43d0070"
}

# Sensitive: the data.gov.in API key. Never committed. Enter it when
# `specific dev` or `specific deploy` prompts for it, or set it in
# specific.local for local development.
secret "market_api_key" {}
