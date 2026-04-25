# astrbot_plugin_memory_manager

设计：叶枔枖  
编写：沈砚清

AstrBot 综合记忆管理插件。使用 SQLite 保存分类记忆，支持关键词/简单语义浮现、核心记忆、已解决标记和衰减状态查看。

> 本仓库已隐藏个人联系方式、私有 ID、群号、服务器信息、真实私有记忆内容等个人信息，仅保留通用插件代码。

## 指令

```text
/memory save <分类> <内容>
/memory query <分类>
/memory search <关键词>
/memory semantic <查询文本>
/memory surface
/memory count
/memory core <ID>
/memory resolve <ID>
```
