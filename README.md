# AstrBot 上下文注入系统

设计：叶枔枖  
编写：沈砚清

本仓库为 AstrBot 上下文注入系统公开版实现，包含三个插件：

| 插件 | 作用 |
|---|---|
| `astrbot_plugin_memory` | 跨会话持久化记忆：Soul、用户画像、历史索引、备忘录、TODO。 |
| `astrbot_plugin_memory_manager` | SQLite 记忆管理：分类记忆、关键词/简单语义浮现、衰减状态。 |
| `astrbot_plugin_llmperception` | 环境感知注入：时间、时段、星期、平台信息。 |

> 本仓库已隐藏个人联系方式、私有 ID、群号、服务器地址、密钥等个人信息，仅保留通用插件代码与配置示例。

## 安装

把三个 `astrbot_plugin_*` 文件夹分别放入 `/AstrBot/data/plugins/`，然后重启 AstrBot 或在 WebUI 重载插件。
