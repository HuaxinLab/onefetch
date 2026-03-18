# OneFetch

**语言 / Language**: [中文](../README.md) | [English](./README.en.md)

OneFetch is an agent-facing web reading skill.

Supported sources:
- Xiaohongshu
- WeChat Official Account pages
- Generic HTML pages (including JS-heavy pages)

Default use case is fast reading: fetch cleaned full text and let the LLM summarize.

## Clone

```bash
git clone https://github.com/HuaxinLab/onefetch.git
cd onefetch
```

## Purpose

- Provide a stable, unified web-reading capability for agents.
- Return cleaned body text for LLM summarization, translation, and deeper analysis.
- Prefer cache-first reading by default to avoid repeated crawling.

## Typical Use Cases

- Let an agent read and summarize a WeChat Official Account article.
- Let an agent fetch a Xiaohongshu post, with comments when needed.
- Let an agent handle generic webpages in the same unified flow.
- Store content only after the user explicitly confirms.

## Install Into Agent (Recommended)

Most users do not need to run crawler scripts directly. The common path is to install OneFetch as a skill for the agent.

Example for Codex:

```bash
ln -s <project-root> ~/.codex/skills/onefetch
```

After installation, tell the agent (this is all non-technical users need):
- "Read this webpage: <URL>"
- "Summarize this WeChat article"
- "Fetch this Xiaohongshu post and list key points"

## Common Scenarios

- Scenario 1: Quick first-pass reading
: "Read this webpage and summarize it in 3 key points: <URL>"

- Scenario 2: Valuable content, save it
: "Organize this content and save it."

- Scenario 3: Agent says body is saved but structured summary may be inaccurate
: "Use the saved full text and regenerate summary and tags." (No need to refetch URL)

- Scenario 4: You want the latest page content
: "Refresh this URL first, then re-organize and save it: <URL>"

## Plugin Capabilities (For End Users)

You do not need to provide low-level parameters (callback/regex).  
Describe your goal in natural language, and the agent will choose/test the right plugin.

Available capability types:
- Element extraction: fetch a specific `src/href/text` from a page
- JSONP field extraction: fetch one field from a callback payload
- Chain extraction: HTML -> JS -> JSONP -> target field

Built-in preset families (for agent reuse):
- `template_html_js_jsonp`: template-only preset for learning/writing new presets
- `chain_cdn_js_jsonp_img`: image URL focused extraction
- `chain_cdn_js_jsonp_download`: download URL focused extraction
- `chain_generic_js_jsonp_value`: quick probing for unknown sites
- `chain_js_only_jsonp_value`: use when JS URL is already known

How to ask the agent:
- "Get the download button link from this page: <URL>"
- "This page has a dynamic image. Extract the final image URL: <URL>"
- "Extract `img_url` from this callback response: <URL>"

If extraction fails, the agent should return a concise reason and concrete next-step suggestion.

## Directory Layout

- `SKILL.md`
- `scripts/`
- `references/`
- `onefetch/`
- `tests/`

## Documentation Entry

- This page is the user usage guide (agent-first scenarios).
- Docs index: [references/INDEX.md](./INDEX.md)
