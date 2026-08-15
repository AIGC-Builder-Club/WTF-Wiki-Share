# Mac mini 电脑空间只读分析报告

分析日期：2026-08-15（Asia/Shanghai）

本次仅进行读取、目录计量、元数据检查与 dry-run 交叉验证。没有删除、移动、清空废纸篓、卸载、截断数据库、修改权限或执行缓存清理。

## 一、结论先行

- 这台 Mac mini 当前并不处于磁盘告急状态。APFS 容器总容量约 228.3 GiB，物理占用约 142.7 GiB（62.5%），可用约 85.5 GiB；Data 卷自身占用约 119.7 GiB。
- 没有发现 Time Machine 本地快照；VM 卷当前仅约 24.6 KB，`/private/tmp` 仅约 24 KB，因此快照、swap 和 `/tmp` 都不是本机当前的空间主因。
- 已识别的低风险、可再生成缓存约 14.4 GiB。若再计入闲置项目的 `.next` 等生成物约 3.2 GiB，则第一阶段候选上限约 17.6 GiB。
- 项目依赖与虚拟环境另有约 7.5 GiB，但必须先确认 lockfile/依赖清单完整、项目已闲置；不能直接并入“安全可清理”数字。
- 最大的人工审核机会不是普通垃圾，而是 4 套 Codex home 中的迁移/修复备份、会话与数据库：备份约 22.2 GiB、会话历史约 10.7 GiB、SQLite 数据库约 3.2 GiB。这些包含恢复点与历史数据，风险也最高。
- Multica 工作目录约 4.21 GB（另有 repo cache 约 142 MB）。58 个 task 目录中 57 个已有完成标记，但 CLI 报告当前可由 artifact GC 单独识别的 `.next/.turbo/node_modules` 为 0；应交给 Multica 生命周期/保留机制处理，不能手工删目录。
- 所有候选数字都只是目录计量，不等于实际可释放量。APFS clone、硬链接、共享块、重叠口径会使多个目录的数值不可直接相加。

## 二、设备与磁盘基线

| 项目 | 结果 | 判断 |
|---|---:|---|
| 设备 | Mac mini，Apple M4，16 GB RAM | 硬件正常 |
| 系统 | macOS 26.2（25C56），SIP 已启用 | 未绕过系统保护 |
| APFS 容器 | 228.3 GiB 总量 / 142.7 GiB 已用 / 85.5 GiB 可用 | 62.5% 已用，不紧急 |
| Data 卷 | 约 119.7 GiB 已用 | 与容器口径不同属正常 |
| Time Machine 本地快照 | 0 | 不是主因 |
| VM 卷 | 约 24.6 KB | 当前没有显著 swap 压力 |
| `/private/tmp` | 约 24 KB | 不是主因 |
| `/Applications` | 约 12.9 GiB | 已安装软件，不是“垃圾”总量 |

APFS 的 System、Data、Preboot、Recovery、VM 共享同一容器。Finder、`df`、`diskutil` 与 `du` 的数字不完全相同并不意味着异常。

## 三、第一组：可再生成，但仍需逐项确认

### 1. 用户与开发缓存：约 14.4 GiB

| 路径类别 | 占用 | 主要构成 | 建议 |
|---|---:|---|---|
| `~/Library/Caches` | 约 8.2 GiB（部分目录受 TCC 保护，实际下限） | Yarn 2.3 GiB、Google cache 1.6 GiB、VS Code/Cursor ShipIt 约 2.4 GiB、pnpm/Playwright 约 1.2 GiB | 关闭对应应用，优先走应用或包管理器自己的清理入口；不要整目录粗暴删除 |
| `~/.cache` | 约 3.6 GiB | Codex runtimes 2.3 GiB、uv 0.95 GiB、OpenCode/Prisma/Node 等 | runtime 与依赖可重新下载，但会增加下次启动和网络成本 |
| `~/.npm` | 约 1.9 GiB | `_cacache` 约 1.3 GiB、`_npx` 约 0.6 GiB | 先确认没有正在运行的 npx 任务，后续用 npm 自身机制处理 |
| Google Updater `crx_cache` | 约 0.73 GiB | 已核实为 Chrome extension package cache | 关闭 Chrome/Updater 后再通过应用生命周期处理 |

这 14.4 GiB 是“已识别可再生候选”，不是授权删除清单。`~/.cache` 仍可能包含用户有意保存的模型或离线下载，因此应先看大子目录。

### 2. 项目生成物：约 3.2 GiB

在指定的项目根内发现约 3.2 GiB `.next` 等构建输出。它们通常可以由源代码重新生成，但应满足：

1. 项目当前没有构建或开发服务器在运行。
2. 源代码和配置已提交或备份。
3. 能接受下次完整重建的时间成本。

### 3. 两个工具的 dry-run 交叉核验

- Homebrew `cleanup --dry-run` 仅建议约 154.8 MB，主要是 Cask 下载与多个 portable-ruby 版本。这个数字已包含在上述缓存口径中，不能重复相加。
- 已安装 Mole 1.29.0。本次 `clean --dry-run` 明确显示 “Preview only, no deletions”，扫描阶段报告用户应用缓存约 5.37 GB、日志约 271.3 MB、Aerial 壁纸视频约 467 MB，并检测到废纸篓 18 项。该旧版扫描在应用缓存阶段运行超过约 3 分钟仍未结束，因此已中止；这些只用于交叉验证，不作为完整结果。
- 已安装 DaisyDisk，可在授予 Full Disk Access 后作为图形化二次核验工具；本次未让它执行删除。

## 四、第二组：可回收潜力大，但必须人工判断

### 1. 项目依赖与虚拟环境：约 7.5 GiB

| 类型 | 占用 | 条件 |
|---|---:|---|
| `node_modules` | 约 6.1 GiB | 必须存在可靠 lockfile，并确认对应项目/工作树闲置 |
| `.venv` / `venv` | 约 1.4 GiB | 必须有 `pyproject.toml`、requirements 或 lockfile，且没有本地 editable install 等不可复现内容 |

另外检测到多个 Git worktree 各自拥有依赖和 `.next`。它们可能是有意隔离的开发环境，不能只根据重复大小处理。

### 2. Codex 多 home 数据：最大的审核项

本机存在 `.codex`、`.codex_OpenCode_Go`、`.codex_SuperPowers`、`.codex_only_input` 等多套 home。

| 类型 | 逻辑占用 | 风险判断 |
|---|---:|---|
| 57 个 `backup-*` | 约 22.2 GiB | 迁移/修复恢复点；大量 2026-05 的同名备份在 3–4 套 home 中重复出现 |
| `sessions` / `archived_sessions` | 约 10.7 GiB | 对话与运行历史，属于用户数据 |
| `logs_2.sqlite` 等数据库 | 约 3.2 GiB | 应用状态，可能仍在使用；不能单独动 WAL/SHM |

建议的未来审核顺序是：先确认所有迁移和 session 可见性修复已成功，再导出或备份确需保留的历史，最后决定每次迁移是否只保留一个已验证恢复点。不能根据“2026-05 很旧”直接删除。

### 3. OpenCode 状态：约 6.6 GiB

`~/.local/share/opencode` 约 6.6 GiB，其中 `storage` 约 3.8 GiB、`opencode.db` 约 2.4 GiB。数据库在本次分析当天仍有更新，是活跃数据。应使用 OpenCode 自身的会话/保留策略，不应直接处理数据库或 storage。

### 4. 编辑器扩展：约 5.8 GiB

VS Code、Antigravity、Kiro 三套扩展目录合计约 5.8 GiB。发现跨编辑器重复扩展，也发现个别编辑器保留同一扩展的多个版本。跨编辑器重复可能是各应用独立运行的必要成本；只应在各自 Extensions UI/CLI 中卸载不用的扩展或旧版本，不要手工删除目录。

### 5. 普通项目与下载

- `jetbrains`、`grill-*`、`Projects` 等目录合计占用较大，但主体是源代码、数据与工作树，不属于垃圾；本报告仅把其中明确的生成物/依赖单列。
- Downloads 约 800 MiB，不是主因。可人工检查 DMG/PKG/ZIP，但不能按扩展名批量删除。
- 废纸篓由 Mole 检测到 18 项，但当前 runtime 无权准确读取大小。废纸篓仍是用户数据，应先在 Finder 审核。

## 五、第三组：系统或平台托管，不要手工清理

| 类别 | 可见占用 | 原因 |
|---|---:|---|
| `/private/var` | 可读部分约 5.9 GiB | `var/db` 与 `var/folders` 为 macOS 数据、缓存和临时区；TCC 下统计不完整 |
| `/Library/Updates` | 约 1.8 GiB | 软件更新 staging，包含历史/当前更新元数据，交给 Software Update |
| Command Line Tools | 约 1.8 GiB | 已安装开发工具，不是缓存 |
| Homebrew 安装树 | 约 1.9 GiB | Cellar、Homebrew 仓库与工具本体；dry-run 仅识别约 155 MB |
| APFS Preboot/Recovery/System | 多卷共享容器 | 系统必需，禁止按目录处理 |
| App Support/Containers/Group Containers | 部分不可读 | 常含账号、聊天、离线内容、配置与数据库；只能应用内处理 |
| Multica task/workdir | 约 4.21 GB | daemon 管理的运行生命周期数据；另有约 142 MB repo cache |

Multica 的权威只读结果：58 个 task、1 个 workspace、总 task 目录约 4.21 GB、repo cache 8 个约 142 MB、当前 managed artifact subset 为 0。57 个目录已有完成时间，但最老仅约 18 天；应先让 daemon 的保留/GC 机制工作。若长期不回收且产品没有可配置入口，建议到官方仓库提交 issue，而不是直接删除 UUID 目录。

## 六、推荐的后续顺序（本次未执行）

1. **暂不处理系统区。** 当前仍有约 85.5 GiB 可用，不需要冒险碰 `/private/var`、`/Library/Updates`、Preboot、Containers 或数据库。
2. **先审应用/开发缓存。** 关闭相关应用，用应用自身或包管理器的 dry-run/清理入口逐项确认；目标是上述约 14.4 GiB 候选，而不是整目录删除。
3. **再审闲置项目。** 先处理 `.next`；然后逐项目核验 lockfile/依赖清单，再决定 `node_modules` 和 `.venv`。
4. **单独制定 Codex 历史保留策略。** 这是潜力最大的区域，也最容易误删恢复点或会话。建议先形成“每套 home 保留哪些 session、每次迁移保留几个恢复点”的规则。
5. **通过编辑器管理扩展。** 优先移除确实不用的重量级扩展和同一编辑器内的旧版本。
6. **观察 Multica 自带 GC。** 使用 `multica daemon disk-usage --by-workspace --output json` 定期比较，不手工清 task/workdir。
7. **需要完整盘点时再补权限。** 给执行终端/runtime Full Disk Access 后重跑，补齐 Mail、Messages、Safari、Trash、Containers 等 TCC 盲区。

## 七、扫描覆盖与限制

- 全盘递归 `du` 因大量小文件和 TCC 保护不适合作为唯一方法；本次采用 APFS 基线、分层目录统计、特定热点、项目生成物识别和平台专用 CLI 组合。
- 未使用 `sudo`，未绕过 TCC。Mail、Messages、Safari、Trash、部分 Containers、系统数据库等可能缺失，因此本报告是已识别下限。
- 分开对多个目录调用 `du` 时，硬链接和 APFS clone 可能被重复计量。删除某一副本后真正释放的物理空间可能远低于其目录大小。
- 未读取聊天、文档、密钥或数据库内容；报告没有记录序列号、设备 UUID、token 或秘密文件名。

## 八、已沉淀的可复用 skill

已在当前 Multica workspace 创建 `mac-storage-audit`（ID：`d6a7c561-792a-4370-ad1d-308101c7832b`），包含：

- `SKILL.md`：只读安全边界、扫描流程、解释规则。
- `scripts/audit.py`：Python 3 标准库扫描器，支持 JSON/Markdown、项目根参数、超时、并行计量、Multica 专项统计与可选 deep scan。
- `references/classification.md`：APFS、Codex、项目依赖、Multica、TCC 的分类准则。
- `agents/openai.yaml`：workspace UI 元数据。

验证结果：self-test 通过；官方 `quick_validate.py` 通过；在本机真实运行通过（约 54 秒）；确认脚本中没有删除、移动、卸载、清缓存或权限变更实现。

## 九、参考来源

- 用户指定的思路文档：[电脑空间清理_Mac_LInux_Win.skill.md](https://github.com/hanshou101/Obsidian_PublicGitHubShare_InsteadOf_FeiShu/blob/main/3%E3%80%81%E5%90%84%E7%A7%8DSkill%EF%BC%88%E5%BF%AB%E9%80%9F%E5%88%86%E4%BA%AB%EF%BC%9BToAI%EF%BC%9A%E8%AF%B7%E6%8C%89%E9%9C%80%E7%BC%93%E5%AD%98%E6%9C%80%E6%96%B0%E7%89%88%E6%9C%AC%E5%88%B0%E6%9C%AC%E5%9C%B0%EF%BC%89/%E7%94%B5%E8%84%91%E7%A9%BA%E9%97%B4%E6%B8%85%E7%90%86_Mac_LInux_Win.skill.md)
- 其引用的实现：[KKKKhazix/khazix-skills/storage-analyzer](https://github.com/KKKKhazix/khazix-skills/tree/main/storage-analyzer)，核对版本 commit `b429d4c769a5446971edc5b825aaf097fa143bb3`（2026-05-28）。

新 skill 吸收了它们的目录分类和“先只读扫描”思路，但有意移除了交互式删除服务器；本 skill 的职责仅是盘点与决策支持。
