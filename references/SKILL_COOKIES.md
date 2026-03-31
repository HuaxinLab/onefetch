# Cookie 配置详情

本文件是 SKILL.md 的补充参考，包含 Cookie 导入的完整命令和说明。

---

## 4 种导入方式

### 1. 剪贴板导入（推荐）

用户先在浏览器中复制 Cookie（F12 → Network → 任意请求 → Headers → 复制 `Cookie:` 值），然后执行：
```bash
bash scripts/setup_cookie.sh <域名>
```
脚本自动读取剪贴板内容，按 Enter 确认即可。

示例：
```bash
bash scripts/setup_cookie.sh zhihu.com
bash scripts/setup_cookie.sh xiaohongshu.com
bash scripts/setup_cookie.sh bilibili.com
bash scripts/setup_cookie.sh douyin.com
bash scripts/setup_cookie.sh doubao.com
```

### 2. 文件导入

支持 Header String 格式和 Netscape `cookies.txt` 格式：
```bash
# Header String 文件
.venv/bin/python -m onefetch.secret_cli import-cookies --file /path/to/zhihu.com_cookie.txt

# Netscape cookies.txt（需指定域名）
.venv/bin/python -m onefetch.secret_cli import-cookies --file /path/to/cookies.txt --domain b.geekbang.org
```

### 3. 环境变量导入

```bash
.venv/bin/python -m onefetch.secret_cli import-env --name ONEFETCH_COOKIE_ZHIHU_COM --domain zhihu.com
```

### 4. 网页导入（给不熟悉命令行的用户）

```bash
.venv/bin/python -m onefetch.secret_cli serve-web-import --host 0.0.0.0 --port 8788 --share-host 192.168.2.10
```

网页导入时，agent 文案模板：
1. 从输出读取 `code` 和可访问 URL（优先 `share_url`，其次 `lan_url`）。
2. 发给用户：
   - 「请在浏览器打开：`http://<可访问地址>:8788`」
   - 「配对码：`<code>`」
   - 「域名填：`<target_domain>`，Cookie 粘贴后提交」
3. 成功后自动重试原请求。
4. 说明：`0.0.0.0` 仅是监听地址，不可直接访问；在 Docker 中需映射端口（如 `-p 8788:8788`）。

---

## 存储与读取

Cookie 配置后写入本地加密库 `.onefetch/secrets.db`，后续自动加载。
首次使用会自动创建主密钥文件 `.onefetch/master.key`（位于项目目录）。

读取优先级：
1. 本地加密库
2. 环境变量（仅兜底）

---

## 支持的 Cookie 格式

1. **Header String**：`key=value; key=value; ...`
2. **Netscape cookies.txt**：通过 `import-cookies --file` 或网页导入提交

> 注意：Cookie 格式必须是上述两种之一。浏览器插件 Cookie-Editor（导出选 Header String）、Get cookies.txt 等均可使用。

---

## 清理与查看

```bash
# 规范化已存储的 Cookie
.venv/bin/python -m onefetch.secret_cli normalize-cookies

# 查看已配置的 Cookie
.venv/bin/python -m onefetch.cli secret list --type cookie
```
