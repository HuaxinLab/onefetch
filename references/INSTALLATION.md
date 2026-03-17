# 安装与使用

## 路径占位

- `<project-root>`: OneFetch 项目根目录

## 首次安装（推荐）

```bash
cd <project-root>
bash scripts/bootstrap.sh
bash scripts/doctor.sh
```

## 日常使用

默认不存储：

```bash
bash scripts/run_ingest.sh --present "https://example.com"
```

需要存储时：

```bash
bash scripts/run_ingest.sh --store "https://example.com"
```

## 可选能力

强制浏览器渲染：

```bash
ONEFETCH_GENERIC_RENDER_MODE=browser bash scripts/run_ingest.sh "URL"
```

小红书评论：

```bash
ONEFETCH_XHS_COOKIE='...' ONEFETCH_XHS_COMMENT_MODE='state+api' \
  bash scripts/run_ingest.sh "https://www.xiaohongshu.com/explore/..."
```

## 清理与打包

```bash
bash scripts/clean.sh
bash scripts/pack.sh --clean-before
bash scripts/pack.sh --name onefetch.zip --output release
```
