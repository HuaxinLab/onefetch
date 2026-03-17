# OneFetch 安装与使用指南

## 环境要求

- 建议 Python 3.11（支持 3.10+）
- `pip`
- 可选：Playwright（用于 JS 密集页面）

## 环境策略

默认使用虚拟环境（对用户与 agent 都适用）。
不要把依赖直接安装到系统 Python。

## 本地初始化

```bash
cd ~/Projects/acusp/OneFetch
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -e ".[dev]"
```

可选浏览器能力：

```bash
pip install -e ".[browser]"
playwright install chromium
```

## 验证

```bash
onefetch --help
onefetch ingest --help
PYTHONPATH=src python3 -m pytest -q
```

## 运行报告

```bash
onefetch ingest "https://example.com" \
  --report-json ./reports/latest-run.json \
  --report-md ./reports/latest-run.md
```

## TLS 说明

如果你在本地开发环境遇到 TLS 证书问题，可临时使用：

```bash
ONEFETCH_INSECURE_TLS=1 onefetch ingest "https://example.com"
```

仅用于本地调试，不建议长期使用。

默认 TLS 行为：
- OneFetch 默认使用系统信任库（`truststore`）
- 如需强制 `certifi`：

```bash
ONEFETCH_TLS_CERTIFI=1 onefetch ingest "https://example.com"
```

## 小红书评论抓取

说明：
- 匿名模式通常无法稳定访问评论 API
- 若需要评论，建议提供有效登录 Cookie

```bash
export ONEFETCH_XHS_COOKIE='your_cookie_here'
onefetch ingest "https://www.xiaohongshu.com/explore/..."
```

评论模式：

```bash
# 默认（推荐）
export ONEFETCH_XHS_COMMENT_MODE='state+api'

# 含 DOM 兜底（成本更高）
export ONEFETCH_XHS_COMMENT_MODE='state+api+dom'

# 关闭评论抓取
export ONEFETCH_XHS_COMMENT_MODE='off'
```

分页参数（登录态评论 API）：

```bash
export ONEFETCH_XHS_COMMENT_MAX_PAGES=3
export ONEFETCH_XHS_COMMENT_MAX_ITEMS=50
```

风控友好参数：

```bash
export ONEFETCH_XHS_API_MIN_INTERVAL_SEC=1.0
export ONEFETCH_XHS_API_MAX_RETRIES=2
export ONEFETCH_XHS_API_BACKOFF_SEC=1.0
export ONEFETCH_XHS_API_RISK_COOLDOWN_SEC=900
```

当出现风控信号（如 HTTP 461/429，或 API code 300011/300012）时，
OneFetch 会进入冷却期并暂时跳过评论 API。

登录态评论抓取示例：

```bash
export ONEFETCH_XHS_COOKIE='...'
export ONEFETCH_XHS_COMMENT_MODE='state+api'
export ONEFETCH_XHS_COMMENT_MAX_PAGES=3
onefetch ingest "https://www.xiaohongshu.com/explore/..."
```

期望结果（feed metadata）：
- `metadata.comment_fetch.source = api`
- `metadata.comment_fetch.api.count > 0`
- 若 API 返回楼中楼回复，回复会以 `↳ ` 前缀扁平化输出

若要启用 DOM 兜底，请先安装浏览器依赖：

```bash
pip install -e ".[browser]"
playwright install chromium
```

## Skill 安装（Codex）

```bash
ln -s "$(pwd)/skills/onefetch" ~/.codex/skills/onefetch
```

安装后，可通过自然语言触发该 skill。

## Agent 执行顺序（建议）

1. `cd ~/Projects/acusp/OneFetch`
2. `source .venv/bin/activate`
3. `pip install -e ".[dev]"`（仅依赖变更时执行）
4. 运行抓取与测试后再汇报
