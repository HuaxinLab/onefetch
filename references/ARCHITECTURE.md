# Architecture

## Layout

```text
OneFetch/
  SKILL.md
  scripts/
    bootstrap.sh
    doctor.sh
    run_ingest.sh
  onefetch/
    cli.py
    config.py
    models.py
    router.py
    pipeline.py
    storage.py
    adapters/
      base.py
      xiaohongshu.py
      wechat.py
      generic_html.py
  references/
  tests/
```

## Runtime flow

1. User/agent invokes `scripts/run_ingest.sh`.
2. Script ensures environment is ready.
3. CLI routes URL to adapter.
4. Pipeline returns fetched result.
5. Persistence happens only with `--store`.
