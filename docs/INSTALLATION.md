# OneFetch Installation Guide

## Prerequisites

- Python 3.11 recommended (3.10+ supported)
- `pip`
- Optional: Playwright for JS-heavy pages

## Environment policy

Use a virtual environment by default for both users and agents.
Do not install dependencies into system Python for this project.

## Local setup

```bash
cd ~/Projects/acusp/OneFetch
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -e ".[dev]"
```

Optional browser support:

```bash
pip install -e ".[browser]"
playwright install chromium
```

## Verify

```bash
onefetch --help
onefetch ingest --help
PYTHONPATH=src python3 -m pytest -q
```

If you hit local TLS certificate issues in development environments, you can temporarily run with:

```bash
ONEFETCH_INSECURE_TLS=1 onefetch ingest "https://example.com"
```

Use this only for local debugging.

Default TLS behavior:
- OneFetch uses system trust store (`truststore`) by default.
- If needed, force `certifi` bundle:

```bash
ONEFETCH_TLS_CERTIFI=1 onefetch ingest "https://example.com"
```

Xiaohongshu comments:
- Anonymous mode usually cannot access comments API.
- To enable comment fetching, provide a logged-in cookie:

```bash
export ONEFETCH_XHS_COOKIE='your_cookie_here'
onefetch ingest "https://www.xiaohongshu.com/explore/..."
```

Comment fetch mode:

```bash
# default
export ONEFETCH_XHS_COMMENT_MODE='state+api'

# include Playwright DOM fallback
export ONEFETCH_XHS_COMMENT_MODE='state+api+dom'

# disable comment fetch entirely
export ONEFETCH_XHS_COMMENT_MODE='off'
```

For DOM fallback, install browser support first:

```bash
pip install -e ".[browser]"
playwright install chromium
```

## Skill installation (later phase)

```bash
ln -s "$(pwd)/skills/onefetch" ~/.codex/skills/onefetch
```

Then use natural language in Codex to trigger the skill.

## Agent runbook

If an agent runs commands for this project, use this order:

1. `cd ~/Projects/acusp/OneFetch`
2. `source .venv/bin/activate`
3. `pip install -e ".[dev]"` (only when dependencies changed)
4. Run checks/tests before reporting completion
