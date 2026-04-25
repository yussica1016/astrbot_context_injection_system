import re
from datetime import datetime
from pathlib import Path
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.provider import ProviderRequest
from astrbot.api.star import Context, Star, register, StarTools

SAVE_KEYWORDS = ['记一下', '记住', '加入记忆', '保存记忆', '沉淀记忆', '加记忆']
DEFAULT_FILES = {
    'soul.md': '# Soul 设定\n\n（这里填写 AI 的人格、规则、语气风格。）\n',
    'profile.md': '# 用户画像\n\n（这里填写用户长期稳定的信息、偏好和边界。）\n',
    'history_index.md': '# 历史索引\n\n（这里保存历史记录的标题、摘要和标签。）\n',
    'memo.md': '# 备忘录\n\n',
    'todo.md': '# TODO\n\n',
}

def safe_id(x):
    return re.sub(r'[^a-zA-Z0-9_\-]', '_', str(x or 'unknown'))[:80] or 'unknown'

def read(p):
    try:
        return p.read_text(encoding='utf-8')
    except FileNotFoundError:
        return ''

def write(p, s):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(s or '', encoding='utf-8')

@register('astrbot_plugin_memory', '沈砚清', '跨会话持久化记忆插件', '1.0.0', 'https://github.com/yussica1016/astrbot_context_injection_system')
class MemoryPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.data_dir = StarTools.get_data_dir(self.name)
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def user_dir(self, uid):
        return self.data_dir / safe_id(uid)

    def ensure_user(self, uid):
        d = self.user_dir(uid)
        (d / 'history').mkdir(parents=True, exist_ok=True)
        for name, content in DEFAULT_FILES.items():
            p = d / name
            if not p.exists():
                p.write_text(content, encoding='utf-8')
        return d

    @filter.on_llm_request()
    async def inject_memory(self, event: AstrMessageEvent, req: ProviderRequest):
        uid = event.get_sender_id()
        d = self.ensure_user(uid)
        block = f"""

---
# 用户持久化记忆

## Soul 设定
{read(d / 'soul.md')}

## 用户画像
{read(d / 'profile.md')}

## 历史索引
{read(d / 'history_index.md')}

## 备忘录
{read(d / 'memo.md')}
---
"""
        msg = getattr(event, 'message_str', '') or ''
        if any(k in msg for k in SAVE_KEYWORDS):
            block += '\n## 记忆沉淀提醒\n用户可能正在要求保存长期信息。若适合，请调用工具写入。\n'
        req.system_prompt = (req.system_prompt or '') + block

    @filter.llm_tool()
    async def read_todo(self, event: AstrMessageEvent) -> str:
        d = self.ensure_user(event.get_sender_id())
        return read(d / 'todo.md')

    @filter.llm_tool()
    async def update_soul(self, event: AstrMessageEvent, content: str) -> str:
        d = self.ensure_user(event.get_sender_id())
        write(d / 'soul.md', content)
        return 'Soul 已更新。'

    @filter.llm_tool()
    async def update_profile(self, event: AstrMessageEvent, content: str) -> str:
        d = self.ensure_user(event.get_sender_id())
        write(d / 'profile.md', content)
        return '用户画像已更新。'

    @filter.llm_tool()
    async def create_memory(self, event: AstrMessageEvent, title: str, summary: str, content: str, tags: str = '') -> str:
        d = self.ensure_user(event.get_sender_id())
        rid = datetime.now().strftime('%Y%m%d%H%M%S')
        text = f'# {title}\n\n- record_id: {rid}\n- tags: {tags}\n\n## 摘要\n{summary}\n\n## 内容\n{content}\n'
        write(d / 'history' / f'{rid}.md', text)
        with open(d / 'history_index.md', 'a', encoding='utf-8') as f:
            f.write(f'\n- {rid}｜{title}｜{summary}｜tags: {tags}\n')
        return f'已创建历史记忆：{rid}'

    @filter.llm_tool()
    async def add_memo_block(self, event: AstrMessageEvent, content: str) -> str:
        d = self.ensure_user(event.get_sender_id())
        bid = datetime.now().strftime('%Y%m%d%H%M')
        with open(d / 'memo.md', 'a', encoding='utf-8') as f:
            f.write(f'\n<!-- block:{bid} -->\n{content}\n<!-- /block -->\n')
        return f'已新增备忘录：{bid}'
