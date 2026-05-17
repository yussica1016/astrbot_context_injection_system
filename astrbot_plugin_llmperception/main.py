"""
环境感知注入插件
叶枔枖设计，沈砚清编写。
"""
from datetime import datetime
from zoneinfo import ZoneInfo
from astrbot.api import logger
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.provider import ProviderRequest
from astrbot.api.star import Context, Star, register

try:
    import chinese_calendar as chinese_cal
except Exception:
    chinese_cal = None

WEEKDAY_NAMES = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']


def get_period_label(hour: int) -> str:
    """根据小时返回时段标签。"""
    if 5 <= hour < 11:
        return '上午'
    if 11 <= hour < 14:
        return '中午'
    if 14 <= hour < 18:
        return '下午'
    if 18 <= hour < 23:
        return '晚上'
    return '深夜'


@register(
    'astrbot_plugin_llmperception',
    '沈砚清',
    '环境感知注入插件',
    '1.0.0',
    'https://github.com/yussica1016/astrbot_context_injection_system',
)
class LLMPerceptionPlugin(Star):
    def __init__(self, context: Context, config=None):
        super().__init__(context)
        self.config = config or {}
        if isinstance(self.config, dict):
            self.timezone = self.config.get('timezone', 'Asia/Shanghai')
        else:
            self.timezone = 'Asia/Shanghai'

    @filter.on_llm_request()
    async def inject_time_context(self, event: AstrMessageEvent, req: ProviderRequest):
        """在 LLM 请求前注入时间、日期、平台等上下文信息。"""
        try:
            timezone_obj = ZoneInfo(self.timezone)
        except Exception:
            timezone_obj = ZoneInfo('Asia/Shanghai')

        now = datetime.now(timezone_obj)
        context_parts = [
            f'发送时间: {now.strftime("%Y-%m-%d %H:%M:%S")}',
            WEEKDAY_NAMES[now.weekday()],
            get_period_label(now.hour),
        ]

        # 是否感知节假日
        holiday_enabled = isinstance(self.config, dict) and self.config.get(
            'enable_holiday_perception', True
        )
        if holiday_enabled:
            if chinese_cal:
                try:
                    if chinese_cal.is_holiday(now.date()):
                        context_parts.append('法定节假日/休息日')
                    else:
                        context_parts.append('工作日')
                except Exception as e:
                    logger.warning(f"[llmperception] 节假日判断失败: {e}")
            else:
                context_parts.append('周末' if now.weekday() >= 5 else '工作日')

        # 是否感知平台
        platform_enabled = not isinstance(self.config, dict) or self.config.get(
            'enable_platform_perception', True
        )
        if platform_enabled:
            platform_info = (
                getattr(event, 'unified_msg_origin', '')
                or getattr(event, 'platform_meta', '')
                or '未知平台'
            )
            context_parts.append(f"平台: {platform_info}")

        prefix = f"[{' | '.join(context_parts)}]\n"
        req.prompt = f'{prefix}{req.prompt or ""}'
