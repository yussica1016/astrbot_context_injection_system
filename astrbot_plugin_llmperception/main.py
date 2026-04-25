from datetime import datetime
from zoneinfo import ZoneInfo
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.provider import ProviderRequest
from astrbot.api.star import Context, Star, register
try:
    import chinese_calendar as cc
except Exception:
    cc=None
WEEKDAYS=['周一','周二','周三','周四','周五','周六','周日']
def period(h):
    if 5<=h<11: return '上午'
    if 11<=h<14: return '中午'
    if 14<=h<18: return '下午'
    if 18<=h<23: return '晚上'
    return '深夜'
@register('astrbot_plugin_llmperception','沈砚清','环境感知注入插件','1.0.0','https://github.com/yussica1016/astrbot_context_injection_system')
class LLMPerceptionPlugin(Star):
    def __init__(self, context:Context, config=None):
        super().__init__(context); self.config=config or {}; self.timezone=self.config.get('timezone','Asia/Shanghai') if isinstance(self.config,dict) else 'Asia/Shanghai'
    @filter.on_llm_request()
    async def my_custom_hook_1(self,event:AstrMessageEvent,req:ProviderRequest):
        try: tz=ZoneInfo(self.timezone)
        except Exception: tz=ZoneInfo('Asia/Shanghai')
        now=datetime.now(tz)
        parts=[f'发送时间: {now.strftime("%Y-%m-%d %H:%M:%S")}', WEEKDAYS[now.weekday()], period(now.hour)]
        if isinstance(self.config,dict) and self.config.get('enable_holiday_perception', True):
            if cc:
                try: parts.append('法定节假日/休息日' if cc.is_holiday(now.date()) else '工作日')
                except Exception: pass
            else: parts.append('周末' if now.weekday()>=5 else '工作日')
        if not isinstance(self.config,dict) or self.config.get('enable_platform_perception', True):
            parts.append(f"平台: {getattr(event,'unified_msg_origin','') or getattr(event,'platform_meta','') or '未知平台'}")
        req.prompt=f'[{" | ".join(parts)}]\n{req.prompt or ""}'
