
# 每个编程/工程化相关项目-统一规范rule

- 1、应注意，维护一个根的说明文件（而不是看似  存在根目录下的多个文件、却散乱无章、不知道从哪个毛线球的起点梳起），如【README.md】里面、或【分形上下文  skill】方式。内容多、有分支内容的，建议在【根说明文件】做索引。
	- 1.1、分形上下文，本身更新频率较低，优先采用本地的；本地缺失则拉取【 https://github.com/AIGC-Builder-Club/WTF-Wiki-Share/blob/main/3%E3%80%81%E5%90%84%E7%A7%8DSkill%EF%BC%88%E5%BF%AB%E9%80%9F%E5%88%86%E4%BA%AB%EF%BC%9BToAI%EF%BC%9A%E8%AF%B7%E6%8C%89%E9%9C%80%E7%BC%93%E5%AD%98%E6%9C%80%E6%96%B0%E7%89%88%E6%9C%AC%E5%88%B0%E6%9C%AC%E5%9C%B0%EF%BC%89/%E5%88%86%E5%BD%A2%E4%B8%8A%E4%B8%8B%E6%96%87%E7%B3%BB%E7%BB%9F-%E5%89%8D%E6%9C%9F%E8%AE%A8%E8%AE%BA/frac-context-kit/.claude/skills/frac-context/SKILL.md 】的。
	- 1.2、`README.md`文件中，应该详细说明清楚【整个项目文档侧】的组织机制。
		- （至于代码侧的组织细节，一般难以  用单篇文档梳理清楚、而  多篇文档又会有很大的维护成本；  此时，采用【分形上下文  skill】机制，就能很好的平衡    查找成本、最新版本更新频率、上下文长度成本负担    。    ）
			- 常见因为【多时文档】导致的严重误判：
				- 【AME-176】Issue，引用了过时的文档：```  - **一个已知的过期陷阱**：`Awesome_ObsidianPlugin_HugeRepo/docs/Obsidian-Reference-汇总与Bake.md` 第九节写着「本次未能在真实 Vault 上端到端验证」。**这句话是调研当时写的，早已过期。**  ```
					- ————此类，使用【分形上下文  skill】则一般无问题（主要是不会这么言之凿凿——哪怕【后续忘记更新】  AI也可从  分形上下文  拼接出最新的结果、而不是受到过于笃定的自以为未过时的文档  ）。
	- 2、常见索引类型，如：维护手册、更新日志，等等。
- 2、善用CodeX的【Goal目标】功能（或    其它Agent  的同类型机制  ），在计划合理的情况下，【Goal执行目标】经常会有很好的完整效果。
	- 副作用是：如果Goal设定有问题，则长时间的【CodeX Goal】执行，可能会发生严重偏离。
	- 通用型目标（含编程）的设定，可以参照：
		- https://github.com/hanshou101/Obsidian_PublicGitHubShare_InsteadOf_FeiShu/blob/main/2%E3%80%81Goal%E5%88%B6%E5%AE%9A%E3%80%81%E5%BC%80%E6%94%BE%E6%8E%A2%E7%B4%A2%E5%9E%8BGoal%E3%80%81Spec%E5%88%87%E9%9D%A2%E5%93%B2%E5%AD%A6/%E5%85%B3%E4%BA%8EGoal%E5%92%8CSpec%E5%88%87%E9%9D%A2%E5%93%B2%E5%AD%A6%E7%9A%84%E7%BB%84%E5%90%88%EF%BC%88%E5%96%82%E7%BB%99GptPro%E4%BD%BF%E7%94%A8%EF%BC%89/%E3%80%8A%E7%AC%AC%E4%B8%80%E7%AF%87%E3%80%8B%EF%BC%88%E8%A3%81%E5%89%AA%E7%89%88%EF%BC%89%E3%80%8A%F0%9F%9A%80%E5%BC%80%E5%8F%91%E8%80%85%E5%BF%85%E7%9C%8B%EF%BC%81Codex%20%20goal%E5%91%BD%E4%BB%A4%E9%AB%98%E7%BA%A7%E6%8A%80%E5%B7%A7%E4%BF%9D%E5%A7%86%E7%BA%A7%E6%95%99%E7%A8%8B%EF%BC%9APlan%E6%A8%A1%E5%BC%8F%2BSpec-Driven%2B%E8%87%AA%E7%A0%94Skill%20%E4%B8%89%E5%A4%A7%E6%8A%80%E5%B7%A7%E7%BB%84%E5%90%88%E8%AE%A9%E6%95%88%E7%8E%87%E5%80%8D%E5%A2%9E%E3%80%8B.md
	- 偏编程类的（一般必须采用面向Spec编程），可以参照：
		- https://github.com/hanshou101/Obsidian_PublicGitHubShare_InsteadOf_FeiShu/blob/main/2%E3%80%81Goal%E5%88%B6%E5%AE%9A%E3%80%81%E5%BC%80%E6%94%BE%E6%8E%A2%E7%B4%A2%E5%9E%8BGoal%E3%80%81Spec%E5%88%87%E9%9D%A2%E5%93%B2%E5%AD%A6/%E5%85%B3%E4%BA%8EGoal%E5%92%8CSpec%E5%88%87%E9%9D%A2%E5%93%B2%E5%AD%A6%E7%9A%84%E7%BB%84%E5%90%88%EF%BC%88%E5%96%82%E7%BB%99GptPro%E4%BD%BF%E7%94%A8%EF%BC%89/%E3%80%8A%E7%AC%AC%E4%BA%8C%E7%AF%87%E3%80%8BKiroFold%20Single%20Spec%EF%BC%8CKiro%E5%8D%95%E6%96%87%E4%BB%B6%E7%89%88.md.md
- 3、我的Obsidian作为AI平台
	- 目前，我只有一个大的Vault————其下的很多子目录，作为单独的子  GitHub仓库。
	- 目前，以【 https://github.com/hanshou101/2A-META 】为 AI-First 仓库，围绕其为核心打造。
		- 【 https://github.com/hanshou101/Awesome_ObsidianPlugin_HugeRepo 】，为  包含多个SubModulde的【原生/二开Obsidian插件】的一个Macro仓库。

