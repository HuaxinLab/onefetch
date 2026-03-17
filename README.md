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

## 目录结构（Skill 规范）

- `SKILL.md`
- `scripts/`
- `references/`
- `onefetch/`
- `tests/`

## 文档入口

- 本页即用户使用说明（agent 场景）。
- 文档索引：[references/INDEX.md](./references/INDEX.md)
