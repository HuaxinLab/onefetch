# 架构说明（Architecture）

## 1. 设计目标

OneFetch 采用“Skill 外壳 + Python 内核”架构，核心目标：
- 对用户：通过 agent 统一读取网页，不要求懂开发。
- 对工程：平台逻辑可扩展，新增站点不破坏核心流程。
- 对数据：默认 fetch-only，只有用户确认后才持久化。

## 2. 总体结构

```text
OneFetch/
  SKILL.md                # agent 触发与执行规范
  scripts/
    bootstrap.sh          # 环境初始化
    doctor.sh             # 依赖与运行检查
    run_ingest.sh         # 统一执行入口
    setup_xhs_cookie.sh   # 小红书评论 cookie 一次配置
    clean.sh              # 清理缓存/产物（带确认）
    pack.sh               # 打包分享（排除运行产物）
  onefetch/
    cli.py                # 命令入口（ingest）
    router.py             # URL 到 adapter 的路由
    pipeline.py           # 编排：抓取/可选存储/错误分类
    storage.py            # 存储与去重
    models.py             # 统一数据模型
    http.py               # HTTP 客户端与 TLS 策略
    adapters/
      xiaohongshu.py      # 小红书适配器
      wechat.py           # 微信公众号适配器
      generic_html.py     # 通用网页适配器
  references/             # 文档
  tests/                  # 回归测试
```

## 3. 运行流程

1. 用户向 agent 发起“读取网页/抓取链接”请求。
2. agent 按 `SKILL.md` 调用 `scripts/run_ingest.sh`。
3. CLI 提取 URL，交给 router 选择 adapter。
4. adapter 执行抓取与解析，返回统一 `FeedEntry`。
5. pipeline 进行错误分类与结果聚合。
6. 默认返回展示结果；若 `--store` 则落盘到 `data/`。

## 4. 核心边界

### 4.1 scripts（壳层）

职责：
- 环境准备、诊断、调用 CLI、打包与清理。

不负责：
- 平台解析逻辑、数据模型转换。

### 4.2 onefetch（内核）

职责：
- 路由、抓取、解析、错误分类、可选存储。

原则：
- 业务逻辑尽量在 Python 内核，不堆到 shell。

### 4.3 adapter（平台隔离）

- 每个平台一个适配器。
- 平台特殊逻辑（反爬、字段映射、正文清洗）只在对应 adapter 内处理。
- 核心 pipeline 不感知平台细节。

## 5. 数据与输出策略

### 5.1 默认模式（fetch-only）

- 不写入 `data/`。
- 适合先读后决策，避免无效沉淀。

### 5.2 存储模式（--store）

写入：
- `data/raw/*.json`
- `data/feed/*.json`
- `data/notes/*.md`
- `data/catalog.jsonl`

### 5.3 去重策略

- 基于 `canonical_url + content_hash`。

## 6. 错误模型

pipeline 对失败进行分类：
- `route.*`：路由错误
- `network.*`：网络/HTTP/超时
- `risk.*`：风控/限制
- `parse.*`：解析失败
- `unknown`：未分类错误

并输出：
- `error_code`
- `error_type`
- `retryable`

## 7. 可扩展性

新增平台步骤：
1. 增加 `adapters/<platform>.py`
2. 实现 `supports/crawl`
3. 在 CLI 路由注册
4. 增加对应测试（路由 + adapter）

## 8. 为什么采用这套架构

- 比“单脚本抓取”更稳：可测试、可追踪、可扩展。
- 比“多 skill 并存”更清晰：OneFetch 单 skill 入口，减少 agent 歧义。
- 对非开发用户友好：用户通过 agent 使用，脚本细节由 agent 执行。
