# OneFetch

**Language**: [中文](../README.md) | [English](./README.en.md)

OneFetch is an agent-facing web reading skill. Supported sources:
- Xiaohongshu (posts + optional comments)
- WeChat Official Account articles
- Zhihu (column articles + Q&A)
- Bilibili (video subtitle extraction + column articles)
- Generic web pages (including SPA / JS-rendered pages)

Default use case: fetch cleaned body text and let the LLM summarize.

## Clone

```bash
git clone https://github.com/HuaxinLab/onefetch.git
cd onefetch
```

## Purpose

- Provide a stable, unified web-reading capability for agents.
- Return cleaned body text for LLM summarization, translation, and deeper analysis.
- Prefer cache-first reading by default to avoid repeated crawling.

## Install Into Agent (Recommended)

Most users do not need to run crawler scripts directly. Just install OneFetch as a skill for the agent.

Example for Claude Code:

```bash
ln -s /path/to/onefetch ~/.claude/skills/onefetch
```

After installation, tell the agent:
- "Read this webpage: <URL>"
- "Summarize this WeChat article"
- "Fetch this Xiaohongshu post and list key points"

## Supported Platforms

| Platform | Example prompts |
|---|---|
| Xiaohongshu | "Read this Xiaohongshu post: <URL>" |
| WeChat | "Summarize this WeChat article: <URL>" |
| Zhihu | "Read this Zhihu column post: <URL>", "Summarize this Zhihu Q&A: <URL>" |
| Bilibili | "Summarize this Bilibili video: <URL>", "Read this Bilibili article: <URL>" |
| Other pages | "Read this page and summarize in 3 points: <URL>" |

> For SPA / JS-rendered pages (React, Vue, Next.js sites, etc.), OneFetch automatically attempts browser rendering. The agent will install the required browser components on first use.

## Common Scenarios

**Scenario 1: Quick first-pass reading**
> "Read this webpage and summarize it in 3 key points: <URL>"

**Scenario 2: Valuable content, save it**
> "Organize this content and save it."

**Scenario 2b: Save article with images**
> "Save this article including all images."

**Scenario 3: Agent says summary/tags may be inaccurate**
> "Use the saved full text and regenerate summary and tags." (No need to refetch.)

**Scenario 4: You want the latest page content**
> "Refresh this URL first, then re-organize and save it: <URL>"

**Scenario 5: Need Xiaohongshu comments**
> "Fetch this Xiaohongshu post including comments: <URL>"
>
> On first use, the agent will guide you through a one-time Cookie setup.

**Scenario 6: Zhihu column articles need Cookie**
> Zhihu Q&A and answer pages work without Cookie. Zhihu column articles (`zhuanlan.zhihu.com`) require a Cookie — the agent will prompt you to configure it once.

**Scenario 7: Extract/download images from a page**
> "Download the images from this post", "Extract image links from this page"

**Scenario 8: Analyze text and images together**
> "Analyze the text and images in this article" (agent sends both to a multimodal model)

**Scenario 9: Login-required websites**
> "This site requires login, help me set up Cookie."
>
> The agent will guide you to configure a Cookie for that site. Subsequent visits will automatically use the login session.

**Scenario 10: Batch from a table-of-contents page**
> "Use this course index page to fetch all chapters and save them as one collection: <seed_url>"
>
> The agent first discovers content URLs from the seed page, then runs batch ingest/save into one collection folder.

### Cookie Setup

Some platforms and login-required sites need a one-time Cookie configuration (Bilibili video subtitles, Zhihu columns, Xiaohongshu comments, etc.):

1. Log in to the platform in your browser
2. Get the Cookie (choose one method):
   - **F12 DevTools**: Network tab → click any request → Headers → copy the `Cookie:` value
   - **Browser extension**: Cookie-Editor (export as Header String), Get cookies.txt, etc.
3. Copy the Cookie, then run the setup script (it reads from clipboard automatically, just press Enter to confirm)
   - Examples: `bash scripts/setup_cookie.sh zhihu.com`, `xiaohongshu.com`, `bilibili.com`
   - Any website: `bash scripts/setup_cookie.sh example.com` (use the domain name)

> Note: Cookie must be in **Header String** format (`key=value; key=value; ...`), NOT Netscape/curl format.

## Element Extraction (Plugin)

Besides reading full articles, you can ask the agent to extract specific content from a page. No technical parameters needed — just describe your goal:

- "Get the download button link from this page: <URL>"
- "This page has a dynamic image. Extract the final image URL: <URL>"
- "Extract `img_url` from this callback response: <URL>"

If extraction fails, the agent will return a concise reason and suggest next steps.

## Troubleshooting

In most cases the agent handles issues automatically. If a dependency is missing or the environment is broken, the agent will provide the exact fix command — just follow the prompt.

## Optional Extensions

Some websites may have higher-quality dedicated parsers (adapter/expander) maintained in a separate extensions repository.  
Regular users do not need to know command details — just tell the agent your goal, and the agent can check/install/update extensions when needed.

Extensions repository:
- https://github.com/HuaxinLab/onefetch-extensions

## Documentation

- This page is the user guide for regular users.
- Developers / advanced users: see [Documentation Index](./INDEX.md)
