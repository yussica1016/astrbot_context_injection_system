"""
综合记忆管理系统 - Memory Manager 子模块
叶枔枖设计，沈砚清编写。
基于语义相似度的记忆注入与查询。
"""
import re
import sqlite3
from datetime import datetime
from pathlib import Path
from astrbot.api import logger
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.provider import ProviderRequest
from astrbot.api.star import Context, Star, register, StarTools


def now_iso() -> str:
    """返回当前时间的 ISO 格式字符串。"""
    return datetime.now().isoformat(timespec='seconds')


def get_token_set(text: str) -> set:
    """提取文本的字符级和bigram级token集合，用于语义相似度计算。"""
    chars = [c for c in (text or '').lower() if not c.isspace()]
    bigrams = {''.join(chars[i:i+2]) for i in range(max(0, len(chars)-1))}
    return set(chars) | bigrams


def calc_similarity(text_a: str, text_b: str) -> float:
    """计算两个文本的 Jaccard 相似度（基于字符和 bigram）。"""
    tokens_a = get_token_set(text_a)
    tokens_b = get_token_set(text_b)
    intersection = len(tokens_a & tokens_b)
    union = len(tokens_a | tokens_b)
    return intersection / union if union else 0.0


@register(
    'astrbot_plugin_memory_manager',
    '沈砚清',
    '综合记忆管理系统',
    '1.0.0',
    'https://github.com/yussica1016/astrbot_context_injection_system',
)
class MemoryManagerPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.data_dir = StarTools.get_data_dir(self.name)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.db_file = self.data_dir / 'memory_manager.db'
        with sqlite3.connect(self.db_file) as db_conn:
            db_conn.execute(
                'CREATE TABLE IF NOT EXISTS memories('
                'id INTEGER PRIMARY KEY AUTOINCREMENT, '
                'created_at TEXT, category TEXT, content TEXT, '
                'tags TEXT DEFAULT "", importance INTEGER DEFAULT 5, '
                'status TEXT DEFAULT "active", layer TEXT DEFAULT "event", '
                'resolved INTEGER DEFAULT 0)'
            )
            db_conn.commit()

    def get_connection(self) -> sqlite3.Connection:
        """创建并返回数据库连接。"""
        return sqlite3.connect(self.db_file)

    def save_memory(self, content: str, category: str = 'daily', tags: str = '', importance: int = 5) -> str:
        """保存一条记忆到数据库。"""
        with self.get_connection() as db_conn:
            db_conn.execute(
                'INSERT INTO memories(created_at, category, content, tags, importance) '
                'VALUES(?, ?, ?, ?, ?)',
                (now_iso(), category, content, tags, int(importance))
            )
            db_conn.commit()
            new_id = db_conn.execute('SELECT last_insert_rowid()').fetchone()[0]
        return f'已保存记忆 #{new_id}'

    def surface_memories(self, query: str = '', limit: int = 3) -> str:
        """
        语义浮现：根据重要性、layer 和语义相似度排序返回最相关的记忆。
        注意：在内存中排序，适合小数据集。大数据量时应改用 SQL。
        """
        with self.get_connection() as db_conn:
            rows = db_conn.execute(
                'SELECT id, content, category, importance, layer '
                'FROM memories WHERE status="active" AND layer!="archive" '
                'ORDER BY importance DESC, id DESC LIMIT 100'
            ).fetchall()

        scored_items = []
        for row in rows:
            memory_id, content, category, importance, layer = row
            layer_score = 100 if layer == 'core' else 0
            importance_val = importance or 5
            similarity_score = calc_similarity(query, content) * 10
            total_score = layer_score + importance_val + similarity_score
            scored_items.append((total_score, similarity_score, row))

        # 在内存中排序（适用于小型数据集）
        scored_items.sort(key=lambda x: x[0], reverse=True)
        top_items = scored_items[:int(limit)]

        if not top_items:
            return '没有找到记忆。'
        lines = []
        for total_score, sim_score, row in top_items:
            memory_id, content, category, layer = row[0], row[1], row[2], row[4]
            lines.append(
                f'- #{memory_id} [{category}][{layer}] sim:{sim_score:.2f} {content}'
            )
        return '\n'.join(lines)

    def query_memories(self, category: str = None, keyword: str = None, limit: int = 10) -> str:
        """按分类或关键词查询记忆。关键词中的通配符已转义。"""
        sql = 'SELECT id, category, content, tags, layer FROM memories WHERE status="active"'
        params = []
        if category:
            sql += ' AND category=?'
            params.append(category)
        if keyword:
            # 转义 LIKE 通配符
            escaped = keyword.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
            sql += " AND content LIKE ? ESCAPE '\\'"
            params.append(f'%{escaped}%')
        sql += ' ORDER BY id DESC LIMIT ?'
        params.append(int(limit))

        with self.get_connection() as db_conn:
            rows = db_conn.execute(sql, params).fetchall()

        if not rows:
            return '没有找到记忆。'
        lines = []
        for row in rows:
            memory_id, category_name, content, tags, layer = row
            lines.append(f'#{memory_id} [{category_name}][{layer}] {content} tags:{tags}')
        return '\n'.join(lines)

    @filter.on_llm_request()
    async def inject_relevant_memories(self, event: AstrMessageEvent, req: ProviderRequest):
        """在 LLM 请求前自动注入语义关联的记忆。"""
        message_text = getattr(event, 'message_str', '') or ''
        memory_block = self.surface_memories(message_text, 3)
        if memory_block:
            current_prompt = req.system_prompt or ''
            req.system_prompt = (
                current_prompt
                + '\n\n## 语义关联记忆（自动浮现）\n'
                + memory_block
                + '\n'
            )

    @filter.command('memory', alias={'/memory'})
    async def handle_memory_command(self, event: AstrMessageEvent):
        """处理 /memory 命令。"""
        raw_text = (getattr(event, 'message_str', '') or '').strip()
        cleaned = re.sub(r'^/?memory\s*', '', raw_text).strip()
        parts = cleaned.split(maxsplit=2)

        if not parts:
            yield event.plain_result(
                '用法：/memory save/query/search/semantic/surface/count/core/resolve'
            )
            return

        sub_command = parts[0]

        if sub_command == 'save' and len(parts) >= 3:
            yield event.plain_result(self.save_memory(parts[2], parts[1]))
            return

        if sub_command == 'query':
            category_filter = parts[1] if len(parts) > 1 else None
            yield event.plain_result(self.query_memories(category=category_filter))
            return

        if sub_command == 'search' and len(parts) > 1:
            search_keyword = cleaned.split(maxsplit=1)[1]
            yield event.plain_result(self.query_memories(keyword=search_keyword))
            return

        if sub_command == 'semantic' and len(parts) > 1:
            query_text = cleaned.split(maxsplit=1)[1]
            result = self.surface_memories(query_text, 10)
            yield event.plain_result(result or '没有找到记忆。')
            return

        if sub_command == 'surface':
            result = self.surface_memories('', 10)
            yield event.plain_result(result or '暂无记忆。')
            return

        if sub_command == 'count':
            with self.get_connection() as db_conn:
                count = db_conn.execute(
                    'SELECT COUNT(*) FROM memories WHERE status="active"'
                ).fetchone()[0]
            yield event.plain_result(f'当前 active 记忆：{count} 条')
            return

        if sub_command == 'core' and len(parts) > 1:
            try:
                memory_id = int(parts[1])
            except ValueError:
                yield event.plain_result('请提供有效的记忆ID（数字）。')
                return
            with self.get_connection() as db_conn:
                db_conn.execute(
                    'UPDATE memories SET layer="core" WHERE id=?', (memory_id,)
                )
                db_conn.commit()
            yield event.plain_result(f'#{memory_id} 已标记为 core。')
            return

        if sub_command == 'resolve' and len(parts) > 1:
            try:
                memory_id = int(parts[1])
            except ValueError:
                yield event.plain_result('请提供有效的记忆ID（数字）。')
                return
            with self.get_connection() as db_conn:
                db_conn.execute(
                    'UPDATE memories SET resolved=1 WHERE id=?', (memory_id,)
                )
                db_conn.commit()
            yield event.plain_result(f'#{memory_id} 已标记为已解决。')
            return

    @filter.llm_tool()
    async def memory_save(
        self,
        event: AstrMessageEvent,
        content: str,
        category: str = 'daily',
        tags: str = '',
        importance: int = 5,
    ) -> str:
        """保存记忆到数据库。

        Args:
            content(string): 记忆内容
            category(string): 分类
            tags(string): 标签，逗号分隔
            importance(number): 重要度 1-10
        """
        try:
            return self.save_memory(content, category, tags, importance)
        except Exception as e:
            logger.error(f"[memory_manager] memory_save 失败: {e}")
            return f'保存记忆失败: {e}'

    @filter.llm_tool()
    async def memory_query(
        self,
        event: AstrMessageEvent,
        category: str = '',
        keyword: str = '',
        limit: int = 10,
    ) -> str:
        """查询记忆。

        Args:
            category(string): 分类过滤，可空
            keyword(string): 关键词搜索，可空
            limit(number): 返回数量上限
        """
        try:
            return self.query_memories(
                category or None, keyword or None, limit
            )
        except Exception as e:
            logger.error(f"[memory_manager] memory_query 失败: {e}")
            return f'查询记忆失败: {e}'

    @filter.llm_tool()
    async def memory_surface(
        self, event: AstrMessageEvent, limit: int = 3
    ) -> str:
        """主动浮现高相关度的记忆。

        Args:
            limit(number): 返回数量上限
        """
        try:
            return self.surface_memories('', limit)
        except Exception as e:
            logger.error(f"[memory_manager] memory_surface 失败: {e}")
            return f'浮现记忆失败: {e}'
