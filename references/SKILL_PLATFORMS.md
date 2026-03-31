# 平台特殊处理详情

本文件是 SKILL.md 的补充参考，包含各平台的详细处理逻辑。

## 支持的平台

| 平台 | 自动识别的 URL | 说明 | Cookie |
|---|---|---|---|
| 小红书 | `xiaohongshu.com`、`xhslink.com` | 笔记正文 + 可选评论 | 评论需要 |
| 抖音 | `douyin.com/video/*`、`v.douyin.com` | 视频总结 + 完整文字版（通过抖音 AI 助手） | 需要 |
| 微信公众号 | `mp.weixin.qq.com` | 文章正文 | 不需要 |
| 知乎 | `zhuanlan.zhihu.com/p/*`、`zhihu.com/question/*` | 专栏文章、问答 | 专栏需要；问答不需要 |
| B 站 | `bilibili.com/video/*`、`bilibili.com/opus/*` | 视频（AI 字幕）、专栏 | 字幕需要；专栏不需要 |
| 扩展站点 | 由已安装扩展定义（如 `b.geekbang.org`） | 专用解析，噪音更少 | 视站点而定 |
| 通用网页 | 所有其他 URL | 自动去噪提取正文；SPA/JS 页面自动浏览器渲染 | 视站点而定 |

agent 不需要手动选择适配器，CLI 根据 URL 自动路由。短链（如 `xhslink.com`）也会自动展开处理。

---

## 小红书

- 默认不抓取评论。仅在用户需要评论时启用：
  ```bash
  ONEFETCH_XHS_COMMENT_MODE='state+api' \
    bash scripts/run_cli.sh ingest --present "https://www.xiaohongshu.com/explore/..."
  ```
- 评论需要 Cookie，未配置时引导用户配置

### 图片内容识别（豆包 OCR）

很多小红书笔记的核心内容在图片中（图片里是文字），正文 `desc` 可能很短甚至为空。

**判断时机：** 当 ingest 返回的 `full_body` 几乎为空（仅标题+标签）但有多张图片时，提示用户：
「这篇笔记的内容主要在图片里，需要我解析图片中的文字吗？」

**不要自动 OCR**，原因：
- 图片可能很多（10+张），每张需要单独调用豆包 API
- 使用用户个人账号 Cookie，需控制调用频率
- 不是所有图片都包含文字（可能是纯配图）

**操作流程：**

1. 用户确认后，逐张调用豆包 API 提取文字：
   ```bash
   .venv/bin/python scripts/doubao_chat.py "提取图片中的所有文字，保持排版结构：<图片URL>"
   ```
2. **串行调用，每张间隔 2-3 秒**，避免触发风控
3. 将每张图片的 OCR 结果按顺序整合，呈现给用户
4. 如果用户要求，可以 `cache-backfill` 回填到缓存

**用户主动要求时也可以使用：** 用户说「帮我看看图片里写了什么」「解析图片内容」等。

**Cookie 配置：** 豆包 API 需要登录态 Cookie。
首次使用时引导用户配置：`bash scripts/setup_cookie.sh doubao.com`

---

## 抖音

抖音视频通过抖音内置的 AI 助手获取内容，不直接爬取页面。

- **需要 Cookie**：`bash scripts/setup_cookie.sh douyin.com`
- **自动两步获取**：adapter 自动先总结视频内容，再用深度思考模式获取完整文字版
- **支持短链接**：`v.douyin.com` 短链会自动解析为完整 URL
- **输出格式**：body 包含「视频总结」和「完整文字版」两个部分

### 独立脚本（灵活使用）

除了通过 `ingest` 命令自动处理，也可以直接用脚本：
```bash
# 总结视频
.venv/bin/python scripts/douyin_ai.py <视频URL或ID> "总结视频内容"

# 完整文字版（深度思考模式）
.venv/bin/python scripts/douyin_ai.py --deep <视频URL或ID> "给我完整的视频文字版"

# 两步走：总结 + 完整文字版
.venv/bin/python scripts/douyin_ai.py --full <视频URL或ID>
```

### 注意事项

- 抖音 AI 助手对部分视频可能无法返回完整文字版，此时总结仍然可用
- 深度思考模式（`--deep`）耗时更长但结果更完整
- 视频内容分两类：
  - **知识分享类**（类似 B 站）：完整文字版最有价值
  - **画面叙事类**：视频总结更有价值
- Cookie 有效期有限，过期后需重新配置

---

## 知乎

- **问答页面**：无需 Cookie，自动通过 Playwright 渲染获取。默认返回问题 + 高赞 5 个回答（可能截断）。每个回答后标注了 `answer_id`，如需完整内容：
  ```
  https://www.zhihu.com/question/{question_id}/answer/{answer_id}
  ```
- **专栏文章**：需要 Cookie。出现 `error_code=risk.blocked` 时引导配置

---

## B 站

- **视频**：自动通过 API 获取信息和 AI 字幕。字幕需要 Cookie。无 Cookie 时仍可获取标题、作者、简介
- **专栏**：无需 Cookie，自动 Playwright 渲染

---

## 外置扩展

扩展仓库：`https://github.com/HuaxinLab/onefetch-extensions`
（若设置了 `ONEFETCH_EXT_REPO` 环境变量则优先使用）

### 当前可用扩展

| 扩展 ID | 站点 | 提供 | 说明 |
|---|---|---|---|
| `geekbang` | `b.geekbang.org` | adapter + expander | 极客时间课程解析，支持 discover 批量抓取 |

### 扩展管理命令

```bash
# 查看远程可安装的扩展
bash scripts/run_cli.sh ext list --remote --repo "${ONEFETCH_EXT_REPO:-https://github.com/HuaxinLab/onefetch-extensions}"

# 安装扩展
bash scripts/run_cli.sh ext install <ext_id> --repo "${ONEFETCH_EXT_REPO:-https://github.com/HuaxinLab/onefetch-extensions}"

# 更新扩展（已安装但效果异常时）
bash scripts/run_cli.sh ext update <ext_id> --repo "${ONEFETCH_EXT_REPO:-https://github.com/HuaxinLab/onefetch-extensions}"

# 查看已安装的扩展
bash scripts/run_cli.sh ext list

# 移除扩展
bash scripts/run_cli.sh ext remove <ext_id>
```

URL 路由时会自动检测已安装扩展的 adapter，agent 无需手动判断。

若扩展仓库不可用，告知用户：「我可以先按通用模式读取；需要更干净的站点专用结果时，可以在扩展仓库可用后启用专用解析。」
