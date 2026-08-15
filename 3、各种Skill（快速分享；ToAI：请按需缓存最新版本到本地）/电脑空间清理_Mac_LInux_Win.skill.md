
- 可参考的技能：
	- 1
		- 卡兹克  清理垃圾  技能  ：  https://github.com/KKKKhazix/khazix-skills/blob/main/storage-analyzer/SKILL.md

- 之前已有的工具
	- Mac
		- [磁盘空间清理软件、垃圾清理软件](Root/高常用/个人/拾零/技术5/购物清单，【硬件设备】、【硬盘】、【鼠标】、【键盘】、【眼镜】、【背包】，等：/【目录】苹果Apple设备，Apple、Mac、iPad、iPhone%20等等，都在这一篇目录/【Mac%20Mini%20M4%202024】，都在这一篇，总览.md#^bid-6bt9pxf)
			- [Mole（清除了  13.24个G  ）（Mac的磁盘空间清理软件、垃圾清理软件），都在这一篇，总览](Root/高常用/个人/拾零/技术5/购物清单，【硬件设备】、【硬盘】、【鼠标】、【键盘】、【眼镜】、【背包】，等：/【目录】苹果Apple设备，Apple、Mac、iPad、iPhone%20等等，都在这一篇目录/【Mac%20Mini%20M4%202024】，都在这一篇，总览/Mole（清除了%20%2013.24个G%20%20）（Mac的磁盘空间清理软件、垃圾清理软件），都在这一篇，总览.md)
			- [【DaisyDisk】（Mac清理工具、磁盘释放工具）（清除了  15.5个G  ）（效果比预计的好。  安装很费神。  ），都在这一篇，总览](Root/高常用/个人/拾零/技术5/购物清单，【硬件设备】、【硬盘】、【鼠标】、【键盘】、【眼镜】、【背包】，等：/【目录】苹果Apple设备，Apple、Mac、iPad、iPhone%20等等，都在这一篇目录/【Mac%20Mini%20M4%202024】，都在这一篇，总览/【DaisyDisk】（Mac清理工具、磁盘释放工具）（清除了%20%2015.5个G%20%20）（效果比预计的好。%20%20安装很费神。%20%20），都在这一篇，总览.md)
	- Windows
		- [Win【系统磁盘空间】软件，C盘空间清理软件、垃圾清理、磁盘空间清理、空间释放、磁盘已满，都在这一篇了，总览](Root/高常用/个人/拾零/技术12/各种软件、应用软件、Windows软件，都在这一篇，总览：/Win【系统磁盘空间】软件，C盘空间清理软件、垃圾清理、磁盘空间清理、空间释放、磁盘已满，都在这一篇了，总览.md)
			- 摘取内容：
				- `  Advanced SystemCare、DISM、黑域、绿色守护、TuneUp、CCleaner、软媒魔方，等等  `
		- [Windows · 垃圾文件清理 · (1) 基本清理](Root/高常用/个人/拾零/技术12/各种软件、应用软件、Windows软件，都在这一篇，总览：/Win【系统磁盘空间】软件，C盘空间清理软件、垃圾清理、磁盘空间清理、空间释放、磁盘已满，都在这一篇了，总览/Windows%20·%20垃圾文件清理%20·%20(1)%20基本清理.md)
			- 摘取内容：
				```
				【C:\Users\Administrator\AppData\Local\Borderlands 3\Saved】
				【C:\Program Files (x86)\Google\Update\Download】
				【C:\ProgramData\Microsoft\ClickToRun\ProductReleases】
				【C:\ProgramData\NVIDIA Corporation\Downloader\哈希串的文件】
				【D:\Program_Files\MiaoYing\Wondershare\万兴喵影\log】
				Steam平台缓存
				Ditto的【缓存数据库】
				【WallPaperEngine】的壁纸文件
				```



- 针对【Multica】平台的特定清理
	- 各种Runtime（MacMini、Linux服务器）
		- 1、【/tmp】目录
		- 2、下载的GitHub临时仓库、及多个checkout、分支branch、worktree等等。
		- 3、各个multica  的工作空间，里面存放的临时性内容。
	- 私有化部署  Multica  平台 （如DX公司内网部署）
		- 1、


- 1

# 示例

## 示例结果一：一台重负载的MacMini

核心结论：这台 Mac mini 当前不紧急，APFS 容器约 228.3 GiB，已用 142.7 GiB（62.5%），可用 85.5 GiB；没有 Time Machine 本地快照，/private/tmp 和 VM/swap 也不是主因。
- 已识别的低风险、可再生成缓存约 14.4 GiB；再加闲置项目 .next 等生成物约 3.2 GiB。两者是候选上限，仍需关闭对应应用、逐项确认。
- 项目 node_modules 与 .venv 约 7.5 GiB，只有 lockfile/依赖清单完整且项目闲置时才可考虑重建。
- 最大的人工审核项是 4 套 Codex home：57 个迁移/修复备份约 22.2 GiB、会话历史约 10.7 GiB、SQLite 数据库约 3.2 GiB。这是恢复点和用户历史，不能按年龄直接删除。
- VS Code/Antigravity/Kiro 扩展合计约 5.8 GiB，应通过各编辑器管理旧版本；OpenCode 状态约 6.6 GiB 且当天仍活跃，不能直接动数据库或 storage。
- Multica 权威统计为 58 个 task 目录约 4.21 GB，另有 8 个 repo cache 约 142 MB；57 个目录已有完成标记，但当前 artifact GC 可单独识别量为 0。应交给 Multica 生命周期/保留机制，不手工删 UUID workdir。
- macOS TCC 阻止了 Mail、Messages、Safari、Trash、部分 Containers 等目录的完整计量，因此报告是已识别下限；APFS clone/硬链接也使各项数字不可直接相加。
已在 workspace 创建可复用 skill：mac-storage-audit（ID：d6a7c561-792a-4370-ad1d-308101c7832b）。它包含 Python 3 标准库扫描器、APFS/Codex/项目/Multica 分类规则，且刻意不包含删除实现。self-test、官方 skill 校验和本机真实运行均已通过。

附件：
- mac-storage-analysis-2026-08-15.md：完整中文分析、目录分级、交叉核验、后续优先级与覆盖限制。
- mac-storage-audit.skill：可导入归档；workspace 中也已注册同名 skill。
	- 见  [mac-storage-audit/SKILL.md](Root/_外部Publish/3、各种Skill（快速分享；ToAI：请按需缓存最新版本到本地）/电脑空间清理_Mac_LInux_Win.skill/mac-storage-audit/SKILL.md)







- 1