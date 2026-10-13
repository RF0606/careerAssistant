# Career Assistant

An evidence-based career workflow for **Codex and Claude Code**: build your personal
profile, set job preferences, find and score roles, tailor a one-page English resume,
and run applications you authorize. 中文或英文对话均可，简历输出为英文。

**发布内容只包含 standard 基础能力**：通用程序、标准流程、空白数据结构、
固定简历模板和虚构测试材料。个人职业知识、偏好、岗位 routes 和 resume-tailor
skills，由用户下载后在自己的本地工作区逐步完善；这些内容不回写到共享源码或发布包。

**v0.1.8 验收状态：开发预览，尚未达到双宿主完整公开发布标准。**
核心、安装、模拟投递和 PDF 已验证；Codex 的旧 CLI 与测试启动参数问题已修复，
实际初始化、事实保存、续接、私人 routes/skill 生成调用和一页 PDF 试跑已通过。
已有 Windows/Linux 普通权限冷启动验证，以及 Codex 内置浏览器中的模拟登录、上传、
授权提交、确认回写和不确定结果续接。本版加入本地备份、恢复、修改记录和数据迁移，
以及三系统 CI 和版本预览发布流程。macOS 桌面宿主尚未实机验证；Claude Code 暂缓，
此前 OAuth 401 尚未处理。真实 Workday 等网站仍须在用户自己的环境核实。
详细证据和复测步骤见 [验收记录](docs/VALIDATION.md)。

## 下载后的第一步 / Start here

源码仓库：[RF0606/careerAssistant](https://github.com/RF0606/careerAssistant)，默认分支为 `master`。

1. 在 GitHub 点击 **Code → Download ZIP** 并解压，或 clone 仓库。打开包含本 README 的项目根目录。
2. 在 **Codex** 中把这个文件夹添加为项目；或在 **Claude Code** 中进入这个目录开始会话。
3. 输入：**“帮我初始化信息”**，或 **“Help me initialize my career profile.”**

助手会读取项目指令，逐步建档；你不需要先填 JSON 或了解 skill 命令。
如果宿主只允许读取文件，先为这个工作区启用文件写入与命令执行；助手会说明
受限的具体步骤。Claude Code 提示 401 时，需要先恢复其本地登录。
若选择从 skill 列表显式调用，或想安装到另一个项目，可以运行：

```text
python install.py --host codex
python install.py --host claude
python install.py --host both --workspace <your-career-workspace>
```

安装默认只作用于指定项目。需要跨项目安装时使用 `--scope user`。
可只复制 `skills/career-assistant/` 到宿主的个人 skills 目录；该文件夹是自包含的。
Codex 使用 `.agents/skills/`，Claude Code 使用 `.claude/skills/`。
已有不同版本时安装器停止；检查差异后用 `--replace` 备份再替换。
若新 skill 未出现在列表中，重新打开会话；当前对话也可按文件读取并执行它。
升级已有安装时，助手按当前宿主检查并运行 `python install.py --host codex --replace`
或对应的 claude/both 选项，旧版会备份。
也可显式调用 Codex 的
`$career-assistant` 或 Claude Code 的 `/career-assistant`。

### 基础环境

核心建档脚本仅需 Python 3.10+（可使用宿主提供的本地运行时），无需 API 密钥或
单独的模型服务。你需要自己可用的 Codex 或 Claude Code 账户。PDF 功能另需
[Tectonic](https://tectonic-typesetting.github.io/en-US/install.html) 与以下 Python 包：

```text
python skills/career-assistant/scripts/career.py doctor --host codex --probe-writes
```

如果缺少 PDF 或浏览器工具，仍可先完成资料收集；助手会解释后续缺少什么。
PDF 依赖安装在本项目的 `.venv`，直接调用其中的 Python，不需要管理员权限或修改
PowerShell 执行策略。首次 TeX 下载失败或缺缓存时，简历保留为 draft。
新电脑的具体引导见 [冷启动说明](docs/COLD_START.md)。
若需要文件路径、Python 安装或权限方面的帮助，直接把错误告诉助手。
Codex 初始化被拒绝时，先看 [Codex 权限与 CLI 排查](docs/CODEX_SETUP.md)。
验收脚本会保留本机 Windows 沙箱配置；PATH 选到旧版 CLI 时可用 `--executable` 指定已验证的版本。

## 功能与使用方式

| 功能 | 可以直接说 |
|---|---|
| 分步建立职业档案 | 帮我初始化信息，我有一份现有简历。 |
| 从零建档 | 我没有简历，请从最近一份工作开始帮我整理。 |
| 恢复或更新资料 | 继续上次的初始化。／更新我的最近一份工作经历。 |
| 配置求职偏好 | 我想找业务分析岗位，请帮我设置地区、薪资和远程偏好。 |
| 建立岗位专属 skill | 根据我的经历和这份 JD，建立这个方向的 resume-tailor skill。 |
| 搜索与评分 | 按我的偏好找 5 个岗位，说明匹配依据和缺口。 |
| 定制简历 | 根据这份完整 JD 帮我生成一页英文简历。 |
| 展示项目经验 | 这份简历加入 Projects，放在 Work Experience 下方。 |
| 自动投递 | 帮我申请这 3 个已筛选岗位，每份提交前让我确认。 |
| 批次投递 | 我批准提交这批已确认岗位，最多 3 份，按我的限制执行。 |
| Workday 登录 | 为我创建 Workday 凭据文件目录，告诉我在哪里填写。 |
| 查看申请状态 | 告诉我哪些申请已提交，哪些需要我处理。 |
| 备份职业资料 | 帮我备份当前资料，告诉我保存在哪里。 |
| 恢复私人备份 | 把这份本地备份恢复到这个空工作区。 |
| 查看修改记录 | 我的职业档案和偏好最近改了哪些内容？ |
| 升级旧数据 | 保留我的资料，帮我升级数据格式。 |

支持用户选择的任意岗位方向；岗位指导根据你的真实经历和目标 JD 生成，
在你选择方向、保存偏好后，创建私人 routes 文档和个人岗位 skill。
没有 JD 时可以先建档和设置暂定方向；
不会给只有标题的岗位编造精确分数。首次入门不等于同意投递申请。

## 初始化流程

助手每轮最多问三个相关问题，并保存已经确认的信息：

1. **环境检查**：识别宿主、目录、PDF 与浏览器能力。
2. **材料导入**：提供文本、Markdown、可提取文本的 PDF 或 DOCX。
   没有简历也可以口述。扫描件无法提取时需要提供文本。
3. **事实整理**：工作、项目、教育、技能和成果；区分材料记载、本人确认、估算和待确认。
4. **投递偏好**：目标方向、地点、薪资与币种、工作许可、远程/通勤、合同、出差和排除条件。
5. **岗位配置**：根据你选定的方向和偏好，创建私人 routes 文档、个人方向配置和 resume-tailor skills；后续可以新增方向。
6. **自动投递设置**：你选择每份提交前确认或每批授权一次；配置浏览器和需要的账号登录。
7. **JD 试跑**：看一次评分、简历和缺口，修正后开始日常使用。

可跳过非必需问题，关闭后继续。重复“初始化”会恢复进度，不清空已有档案。
确认过的经历不会被悄悄改写。资料、偏好、岗位配置或私人 route 更新后，
受影响的评分和简历需要重新生成并检查；旧材料不能继续用于投递。
只修复个人 skill 安装、没有改变岗位内容时，不会让已有评分失效。

项目不会预装个人岗位 routes。初始化时，助手先询问目标岗位和求职偏好，
再为选定方向创建 `.career-assistant/routes/<方向>.md`，内容包含该方向的经历重点、
写作指导和 JD 来源。文档只保存在被忽略的私人目录中，续接时保留已有内容。

对应的个人岗位 skill 按选定宿主生成在 `.agents/skills/career-resume-<方向>/` 或
`.claude/skills/career-resume-<方向>/`；要求两个宿主时生成两份。它会读取私人 routes、最新偏好和事实来源，
不在 skill 中复制姓名、联系方式或工作经历。可以直接说“调用我的 software 岗位 skill
给这份 JD 评分并生成简历”；助手也会在方向匹配时读取相应个人 skill。

生成中途失败时，助手会保留岗位配置、route 和安装进度，说明缺失文件及具体
写入问题；所有选定宿主的个人 skill 均通过文件校验后，才完成岗位配置这一步。
修复权限或路径冲突后，直接说“继续初始化”，助手即可从已保存的进度重试。
旧版本没有安装记录的岗位需要刷新；旧评分没有岗位指纹时需要重新评分，
升级不会清空已有资料。已经点击提交但结果未明的申请仍须核查原尝试，不能重复提交。

## 简历格式

US Letter、一页、英文；结构为页头、**Summary → Skills → Work Experience → Education**。
字体、页边距、分节样式和列表布局来自固定模板。内容由你的资料与 JD 定制。
**Projects 默认关闭**；你有项目材料且要求展示时，增加独立区块，位于
**Work Experience 后、Education 前**。一次性要求只影响那份简历。

助手会编译 PDF，检查页数、提取文本并打开预览检查布局。
生成了源文件不代表 PDF 已通过检查；超页时删减内容，保持版式。
不编造职责、数字、证书、项目作者身份或工作许可。

## 评分与搜索

分别报告申请资格、岗位匹配、简历关键词覆盖和个人偏好匹配。
每项附真实证据、差距与未知项。分数是本工具的估算，不能当作招聘方真实 ATS
分数或面试概率。联网搜索取决于宿主工具；也可直接粘贴完整 JD。

## 自动投递与 Workday 登录

提供 LinkedIn Easy Apply、Greenhouse、Lever、Ashby、Workday 及通用表单操作指南。
助手优先使用宿主已有浏览器；没有时按安装说明配置
[Playwright MCP](https://github.com/microsoft/playwright-mcp)。网站和雇主表单可能不同，
验证码、2FA、账号状态不明或未确认的必填事实会交给你处理。

Workday 可以沿用本地文件登录。助手会创建：

```text
.career-assistant/credentials/workday/accounts.txt
```

用本地文本编辑器填写，每行一组，格式是 `username: <用户名>, password: <密码>`。
可以有多组。**这是本地明文文件，请只在自己的电脑上填写，勿贴到聊天或上传。**
助手通过内存助手读取并填表；验证命令仅输出是否有效和组数。
不会把密码打印到对话、保存到档案或打包。无法安全读取的浏览器环境会要求你手动登录。
登录期间不能开启会记录填充值的浏览器 tracing、调试日志或录屏；无法保证时由你手动登录。
内存会话按 Workday 站点记录已尝试的凭据组；只有明确密码拒绝才允许下一组，
遇到 CAPTCHA、2FA、锁定、网络错误或不明结果就停止。
其他网站首次登录/注册由你完成；Workday 新账号注册也需要你的操作或另外明确授权。

你选定的确认方式决定最后提交的流程。只有页面明确确认成功后才记为 Submitted。
断网或点击结果不确定时先核查，避免重复申请。安装工具或初始化本身不会自动提交。
关闭后重新打开，待核查的申请仍保持 Needs user；只有确认页面证据匹配原尝试后才转为 Submitted。
申请状态命令同时提供各状态数量和下一步操作。

Codex 内置浏览器的真实模拟流程见 [宿主浏览器验收说明](docs/HOST_BROWSER_VALIDATION.md)。
批量操作保留同一个工作标签页；新标签或新会话先检查登录状态，不假定会继承。
重新登录后应核查原申请记录，结果未明的申请不能因为换了会话就重新提交。

## 我的数据保存在哪里？

全部保存在当前职业工作区的 **`.career-assistant/`**，包括来源、档案、偏好、
岗位配置、简历、浏览器会话、凭据和唯一申请 tracker。该目录被 Git 忽略。
生成的个人岗位 skills 也被忽略。不同的人使用不同工作区，避免资料串用。

仓库只包含通用程序、规则、模板、虚构示例与测试。发布脚本只打包白名单文件。
更新程序不清除个人数据。可以直接说“帮我备份资料”，助手会在
`.career-assistant/backups/` 生成带清单和 SHA-256 的私人 ZIP；包括档案、来源、
偏好、私人 routes、简历、申请记录和修改历史。**不读取或备份凭据、浏览器会话和
投递授权**，也不包含宿主安装副本。私人备份是明文个人资料，只通过你自己选择的
私人方式保存和迁移；不要上传到聊天或公开 GitHub。

恢复前助手会校验备份、展示变更范围，执行前自动备份当前资料。恢复到另一位用户的
已有工作区会被拒绝；请使用独立空工作区。同一工作区较新的已提交、结果未明申请
与对应材料会保留。旧投递授权会清空，准备中的申请需重新检查和授权。换电脑后助手
重建个人岗位 skills，你重新填写本地凭据、登录浏览器。旧评分和简历如已失效，会要求
重新生成和检查。

档案、偏好、来源索引和岗位指导的修改会保存本地前后快照，直接说“查看最近改动”
即可。v0.1.8 使用数据 schema 2；旧 schema 1 会先备份、生成迁移计划，保留事实和
申请尝试再升级。中断时助手恢复原文件后再继续；未知版本不会被重置。
操作规则见 [本地资料维护](skills/career-assistant/references/data-maintenance.md)。

## 开发、测试与发布

开发者先读 [START_HERE_CODEX.md](START_HERE_CODEX.md)。在项目里说：
“请按 START_HERE_CODEX.md 检查并完善这个项目”。
测试及已验证范围见 [docs/VALIDATION.md](docs/VALIDATION.md)。
真实网站自动投递仍依赖实际账户、浏览器能力、用户授权和当时表单；模拟测试不代表
已经向真实公司投递过。运行 `python -m unittest discover -s tests -v` 检查核心逻辑。
MIT 许可见 [LICENSE](LICENSE)；第三方宿主、浏览器和 LaTeX 依赖遵循各自许可。

维护者审核更改后运行 `python release.py manifest`、`python release.py verify` 和
`python release.py pack --output outputs/career-assistant-v0.1.8.zip`。
打包命令同时生成 `START_HERE.txt`、ZIP 的 `.sha256` 文件与 `SHA256SUMS.txt`。
只分发这些发布文件；测试日志、用户档案、凭据、安装副本和个人 skills 均不在 ZIP 中。

GitHub CI 在 push/PR 时验证 Windows、Linux、macOS 的核心流程和备份迁移，运行模拟
浏览器测试并生成校验过的发行包。版本标签触发同样验证，再上传四个公开发布文件到
GitHub **预发布版本**；流程不持有模型账户或 Workday 凭据。具体步骤见
[发布维护](docs/RELEASING.md)，旧验收记录见 [历史验收](docs/VALIDATION_HISTORY.md)。
