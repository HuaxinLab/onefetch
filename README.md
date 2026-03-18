# OneFetch

**语言 / Language**: [中文](./README.md) | [English](./references/README.en.md)

OneFetch 是一个面向 agent 的网页读取 skill，支持：
- 小红书
- 微信公众号
- 通用 HTML（含 JS 渲染）

默认用于快速阅读：抓取去噪后的正文并交给大模型归纳总结。

## 下载到本地（Clone）

```bash
git clone https://github.com/HuaxinLab/onefetch.git
cd onefetch
```

## 工具作用

- 给 agent 提供统一网页读取能力（而不是依赖不稳定的临时抓取）。
- 返回去噪正文，适合大模型做总结、翻译和深度整理。
- 默认优先复用缓存，避免重复抓取。

## 适用场景

- 快速了解网页主要内容（摘要 + 要点）。
- 对感兴趣内容做进一步翻译或深入分析。
- 用户确认后再做保存/归档。

## 安装到 Agent（推荐）

普通用户不需要自己执行抓取脚本，主要是把 skill 安装给 agent。

示例（Codex）：

```bash
ln -s <project-root> ~/.codex/skills/onefetch
```

安装后直接对 agent 说（普通用户只需要这一步）：
- “读取这个网页：<URL>”
- “总结这条公众号内容”
- “抓这个小红书并输出要点”

## 常见场景与应对

- 场景 1：先快速看内容
: “读取这个网页并总结 3 点：<URL>”

- 场景 2：内容有价值，准备保存
: “把这篇内容整理后保存。”

- 场景 3：agent 提示“正文已保存，但摘要/要点/标签可能不够准确”
: “用刚才保存的正文重新整理摘要和标签。”（不需要重新抓取 URL）

- 场景 4：你怀疑网页已更新，想要最新内容
: “这篇文章先刷新最新内容，再重新整理并保存：<URL>”

## Plugin 能力（给普通用户）

你不需要填写技术参数（如 callback/regex）。  
直接告诉 agent 你的目标，agent 会自行判断并测试。

当前可用能力（由 agent 选择执行）：
- 页面元素提取：某个 `src/href/text`
- JSONP 字段提取：接口回调里的某个字段
- 链路提取：HTML -> JS -> JSONP -> 字段

内置常用 preset（给 agent 复用）：
- `template_html_js_jsonp`：模板示例，用于学习 preset 结构
- `chain_cdn_js_jsonp_img`：偏图片 URL 提取
- `chain_cdn_js_jsonp_download`：偏下载链接提取
- `chain_generic_js_jsonp_value`：未知站点快速试探
- `chain_js_only_jsonp_value`：已知 JS URL 场景

建议你这样和 agent 说：
- “帮我拿这个页面里下载按钮的链接：<URL>”
- “这个页面里有动态图片，帮我提取最终图片 URL：<URL>”
- “这个接口返回里我要 `img_url` 字段，帮我拿到：<URL>”

如果提取失败，agent 会返回失败原因和下一步建议。

## 目录结构（Skill 规范）

- `SKILL.md`
- `scripts/`
- `references/`
- `onefetch/`
- `tests/`

## 文档入口

- 本页即用户使用说明（agent 场景）。
- 文档索引：[references/INDEX.md](./references/INDEX.md)
