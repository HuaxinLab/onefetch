# 插件体系

本文件是 SKILL.md 的补充参考，包含插件的完整文档。

插件用于从页面中提取特定元素（图片 URL、下载链接、CSS 属性、JSONP 字段等），不需要读取完整文章内容。

---

## 核心概念

很多 SPA / JS 渲染页面的数据不需要浏览器就能获取：

```
HTML 页面 → 引用了 JS bundle URL
  → JS bundle → 包含 API 地址或硬编码数据
    → API（通常 JSONP）→ 包含目标值
```

插件沿这条数据链逐层追溯，用正则提取，不需要浏览器，速度快且稳定。

---

## 面对未知页面的推荐流程

```
用户说"帮我提取这个页面的 XXX"
  │
  ├─ HTML 里有目标内容（服务端渲染）？
  │    → extract_css_attr
  │
  ├─ 用户已给出 JSONP 接口地址？
  │    → extract_jsonp_field
  │
  ├─ SPA 页面 / 不确定？
  │    → extract_html_js_jsonp + auto_detect=true 自动探测
  │      → 成功：直接使用
  │      → 失败：plugin doctor 诊断，按 suggestion 调整
```

---

## 插件列表

### `extract_css_attr`
- 从 HTML 中按 CSS 选择器提取属性或文本
- 参数：`selector`（CSS 选择器）、`attr`（默认 `src`，可用 `text`）、`index`（默认 `0`）
- 局限：对 SPA 页面无效

### `extract_jsonp_field`
- 从 JSONP 响应提取字段值
- 参数：`jsonp_url`、`callback`（默认 `callback`）、`field`（默认 `img_url`）

### `extract_html_js_jsonp`（最常用）
- 链路提取（HTML → JS → JSONP → 字段）
- 关键参数：
  - `preset`：内置预设（推荐优先使用）
  - `auto_detect`：`true` 时自动探测数据链路
  - `callback` / `field`：JSONP 回调名和字段名
  - `js_url_regexes` / `jsonp_base_regexes`：自定义正则

---

## 内置 preset

| preset | 用途 | 场景 |
|---|---|---|
| `chain_cdn_js_jsonp_img` | 提取图片 URL | 动态图片 |
| `chain_cdn_js_jsonp_download` | 提取下载链接 | 下载地址 |
| `chain_generic_js_jsonp_value` | 通用字段提取 | 未知站点先用此试探 |
| `chain_js_only_jsonp_value` | 已知 JS URL | 跳过 HTML 定位 |

---

## 插件选型速查

| 场景 | 插件 | 示例 |
|---|---|---|
| HTML 中有目标内容 | `extract_css_attr` | `--opt selector=.hero --opt attr=src` |
| 已知 JSONP 接口 | `extract_jsonp_field` | `--opt jsonp_url=URL --opt field=img_url` |
| SPA 提取图片 | `extract_html_js_jsonp` | `--opt preset=chain_cdn_js_jsonp_img` |
| SPA 提取下载链接 | `extract_html_js_jsonp` | `--opt preset=chain_cdn_js_jsonp_download` |
| 未知站点 | `extract_html_js_jsonp` | `--opt auto_detect=true --json` |
| 提取失败诊断 | `plugin doctor` | `--opt preset=chain_generic_js_jsonp_value --json` |

`--json` 用于获取结构化 JSON 输出，便于 agent 解析和后续处理。

---

## 插件命令

```bash
# 插件列表
bash scripts/run_cli.sh plugin list --with-presets

# CSS 选择器提取
bash scripts/run_cli.sh plugin run extract_css_attr \
  --url "URL" --opt selector=.hero --opt attr=src

# JSONP 字段提取
bash scripts/run_cli.sh plugin run extract_jsonp_field \
  --opt jsonp_url="URL" --opt callback=img_url --opt field=img_url

# 链路提取（preset）
bash scripts/run_cli.sh plugin run extract_html_js_jsonp \
  --url "URL" --opt preset=chain_cdn_js_jsonp_img

# 自动探测
bash scripts/run_cli.sh plugin run extract_html_js_jsonp \
  --url "URL" --opt auto_detect=true --json

# 失败诊断
bash scripts/run_cli.sh plugin doctor extract_html_js_jsonp \
  --url "URL" --opt preset=chain_generic_js_jsonp_value --json
```
