# 命令速查

本文件是 SKILL.md 的补充参考，包含所有命令的完整列表。

---

## 环境初始化

```bash
bash scripts/bootstrap.sh && bash scripts/doctor.sh
```

---

## 主流程（ingest）

```bash
# 默认读取（优先缓存）
bash scripts/run_cli.sh ingest --present --from-cache "URL"

# 刷新内容（实时抓取）
bash scripts/run_cli.sh ingest --present --refresh "URL"

# 保存纯文本
bash scripts/run_cli.sh ingest --store --from-cache "URL"

# 保存文本 + 图片
bash scripts/run_cli.sh ingest --store --with-images --from-cache "URL"

# 图文联合分析
bash scripts/run_cli.sh ingest --present --with-images --from-cache "URL"

# 获取原始 HTML
bash scripts/run_cli.sh ingest --raw "URL"

# 查看可用适配器
bash scripts/run_cli.sh ingest --list-crawlers
```

---

## LLM 回填

```bash
bash scripts/run_cli.sh cache-backfill "URL" \
  --json-data '{"summary":"...","key_points":["..."],"tags":["..."]}'
```

---

## 图片

```bash
bash scripts/run_cli.sh images "URL"
bash scripts/run_cli.sh images --proxy "URL"
bash scripts/run_cli.sh images --download /path/to/dir "URL"
```

---

## 批量抓取

```bash
# 先看发现了哪些 URL
bash scripts/run_cli.sh discover "SEED_URL" --present

# 批量抓取 + 保存 + 图片（完整链路）
bash scripts/run_cli.sh discover "SEED_URL" \
  --ingest --ingest-store --ingest-with-images --ingest-from-cache
```

---

## 抖音视频

```bash
# 通过 ingest 自动获取（总结 + 文字版）
bash scripts/run_cli.sh ingest --present "https://www.douyin.com/video/xxx"
bash scripts/run_cli.sh ingest --present "https://v.douyin.com/xxx/"

# 独立脚本
.venv/bin/python scripts/douyin_ai.py <视频URL或ID> "总结视频内容"
.venv/bin/python scripts/douyin_ai.py --deep <视频URL或ID> "给我完整的视频文字版"
.venv/bin/python scripts/douyin_ai.py --full <视频URL或ID>

# 配置 cookie
bash scripts/setup_cookie.sh douyin.com
```

---

## 小红书评论

```bash
bash scripts/setup_cookie.sh xiaohongshu.com
ONEFETCH_XHS_COMMENT_MODE='state+api' \
  bash scripts/run_cli.sh ingest --present "URL"
```

---

## 豆包聊天（图片 OCR / 多模态）

```bash
# 纯文本聊天
.venv/bin/python scripts/doubao_chat.py "你好"

# 图片内容识别（传 URL）
.venv/bin/python scripts/doubao_chat.py "提取图片中的所有文字，保持排版结构：<图片URL>"

# 指定 cookie 文件
.venv/bin/python scripts/doubao_chat.py --cookie /path/to/cookie "message"

# 配置 cookie
bash scripts/setup_cookie.sh doubao.com
```

---

## 扩展管理

```bash
bash scripts/run_cli.sh ext list --remote --repo "${ONEFETCH_EXT_REPO:-https://github.com/HuaxinLab/onefetch-extensions}"
bash scripts/run_cli.sh ext install <ext_id> --repo "${ONEFETCH_EXT_REPO:-https://github.com/HuaxinLab/onefetch-extensions}"
bash scripts/run_cli.sh ext update <ext_id> --repo "${ONEFETCH_EXT_REPO:-https://github.com/HuaxinLab/onefetch-extensions}"
bash scripts/run_cli.sh ext list
bash scripts/run_cli.sh ext remove <ext_id>
```

---

## Cookie 配置

```bash
# 剪贴板导入
bash scripts/setup_cookie.sh zhihu.com
bash scripts/setup_cookie.sh xiaohongshu.com
bash scripts/setup_cookie.sh bilibili.com
bash scripts/setup_cookie.sh <域名>

# 文件导入（Header String / Netscape cookies.txt）
.venv/bin/python -m onefetch.secret_cli import-cookies --file /path/to/zhihu.com_cookie.txt
.venv/bin/python -m onefetch.secret_cli import-cookies --file /path/to/cookies.txt --domain b.geekbang.org

# 环境变量名导入
.venv/bin/python -m onefetch.secret_cli import-env --name ONEFETCH_COOKIE_ZHIHU_COM --domain zhihu.com

# 网页导入
.venv/bin/python -m onefetch.secret_cli serve-web-import --host 0.0.0.0 --port 8788 --share-host 192.168.2.10

# 清理与查看
.venv/bin/python -m onefetch.secret_cli normalize-cookies
.venv/bin/python -m onefetch.cli secret list --type cookie
```

---

## 浏览器组件安装

```bash
.venv/bin/python -m pip install -e '.[browser]' && .venv/bin/python -m playwright install chromium
```

---

## 扩展联调（仅维护模式）

`bash scripts/smoke_extensions.sh` 仅用于开发/发布前联调，不用于日常用户请求。
