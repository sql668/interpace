# 演示环境配额配置

`demo_limits.json` 是**演示环境**的配额与降本开关。改完保存即生效（最多 5 秒热加载），
**不需要重启服务**。

## 怎么改

直接编辑 `demo_limits.json`。它是标准 JSON，不能写 `//` 注释，所以每个键的说明写在
**下划线开头的兄弟键**里（如 `_token_quota`），程序会忽略它们。

改坏了不用怕：解析失败时服务**保留上一次能用的配置**并打一条 ERROR 日志，
不会因为一个配置文件写错就把整站打挂。

## 生效范围

`enabled` 为 `false`（开发 / 测试 / 正式环境的默认值）时，整套限制完全不生效。
只有演示环境才会打开。

## 各项含义

| 配置 | 含义 |
| --- | --- |
| `per_ip.token_quota` | 每个 IP **累计**可消耗的 token 总量，永不重置。用完这个 IP 就再也用不了 |
| `per_ip.turns_per_day` | 每个 IP 每天最多几轮对话 |
| `per_ip.quizzes_per_day` | 每个 IP 每天最多提交几次答卷 |
| `per_ip.evaluations_per_day` | 每个 IP 每天最多生成几次面试复盘 |
| `per_ip.voice_minutes_per_day` | 每个 IP 每天最多几分钟语音面试 |
| `per_user.max_sessions` / `max_notes` | 单个账号的会话数与笔记数上限，防止把库撑爆 |
| `per_user.max_turns_per_session` | 单个会话最多几轮。**这条最省钱**：上下文越长，每次提问的输入 token 越贵 |
| `interview.max_minutes` | **单场模拟面试最长几分钟**。从面试记录创建算起，语音与文字共用同一个时钟。到点后：语音由服务端主动结束并关闭连接；文字不再回答新问题（直接给提示，不调用模型）。0 = 不限 |
| `global.daily_token_budget` | 所有 IP 合计的每日 token 上限，超出后所有人被拒（真正的钱包兜底） |
| `global.daily_call_budget` | 所有 IP 合计的每日模型调用次数上限 |
| `cost_reduction.disable_background_extraction` | 关掉画像抽取、记忆抽取与合并、会话摘要压缩（用户看不见的额外调用） |
| `cost_reduction.disable_voice_interview` | 彻底关掉语音面试 |
| `cost_reduction.disable_file_upload` | 关掉附件上传（PDF 解析全文很吃 token） |
| `cost_reduction.max_tokens` | 演示环境单次回答的最大输出 token |

## token 是怎么算的

**按 provider 返回的真实用量**记账，不是估算。用的是 `usage_metadata.total_tokens`，
**包含推理过程（reasoning）的 token**——实测这个模型输出 137 token 里有 133 是推理，
只算正文会严重低估成本。

每次模型调用都会往 `usage_records` 表写一行明细（谁、哪个 IP、哪个场景、多少 token），
配额判断就是在这个表上做聚合。
