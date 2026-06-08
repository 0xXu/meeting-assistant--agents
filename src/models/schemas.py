"""
数据模型定义 (schemas.py)

所有 Agent 共用的 Pydantic 数据模型与枚举类型。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


# ============================================================
# 枚举类型
# ============================================================

class MeetingStatus(str, Enum):
    """会议处理状态"""
    PENDING = "pending"
    TRANSCRIBING = "transcribing"
    ANALYZING = "analyzing"
    COMPLETED = "completed"
    FAILED = "failed"


class Priority(str, Enum):
    """任务优先级"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class SentimentType(str, Enum):
    """情绪类型"""
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"


# ============================================================
# 转写模型
# ============================================================

@dataclass
class TranscriptSegment:
    """单条转写片段（含说话人与时间戳）"""
    speaker: str
    text: str
    start: float
    end: float
    confidence: float = 0.0


@dataclass
class TranscriptResult:
    """完整转写结果"""
    meeting_id: str
    segments: list[TranscriptSegment] = field(default_factory=list)
    language: str = "zh"
    duration_seconds: float = 0.0
    full_text: str = ""


# ============================================================
# 行动项模型
# ============================================================

@dataclass
class ActionItem:
    """单条行动项/待办事项"""
    assignee: str
    task: str
    deadline: str = ""
    priority: Priority = Priority.MEDIUM
    context: str = ""
    jira_issue_key: str | None = None
    feishu_task_id: str | None = None


@dataclass
class ActionResult:
    """待办提取结果"""
    meeting_id: str
    action_items: list[ActionItem] = field(default_factory=list)
    sync_status: dict[str, str] = field(default_factory=dict)


# ============================================================
# 会议纪要模型
# ============================================================

@dataclass
class TopicSummary:
    """单个议题摘要"""
    title: str
    discussion_points: list[str] = field(default_factory=list)
    participants: list[str] = field(default_factory=list)
    conclusion: str = ""


@dataclass
class MeetingSummary:
    """完整会议纪要"""
    meeting_id: str = ""
    title: str = "会议纪要"
    participants: list[str] = field(default_factory=list)
    topics: list[TopicSummary] = field(default_factory=list)
    decisions: list[str] = field(default_factory=list)
    next_steps: list[str] = field(default_factory=list)
    duration_minutes: float = 0.0


# ============================================================
# 会议洞察模型
# ============================================================

@dataclass
class SpeakerStats:
    """单个说话人统计数据"""
    speaker: str
    speaking_duration: float = 0.0
    speaking_ratio: float = 0.0
    word_count: int = 0
    segment_count: int = 0


@dataclass
class MeetingInsight:
    """会议洞察分析结果"""
    meeting_id: str = ""
    overall_sentiment: SentimentType = SentimentType.NEUTRAL
    sentiment_score: float = 0.5
    efficiency_score: float = 5.0
    speaker_stats: list[SpeakerStats] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)
    highlights: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)


# ============================================================
# 跟进结果模型
# ============================================================

@dataclass
class FollowUpResult:
    """会后跟进结果"""
    meeting_id: str = ""
    summary_sent: bool = False
    recipients: list[str] = field(default_factory=list)
    jira_issues_created: list[str] = field(default_factory=list)
    feishu_tasks_created: list[str] = field(default_factory=list)
    reminders_scheduled: int = 0
    report_url: str = ""


# ============================================================
# 整体会议状态（LangGraph State）
# ============================================================

@dataclass
class MeetingState:
    """LangGraph Pipeline 全局状态"""
    meeting_id: str
    status: MeetingStatus = MeetingStatus.PENDING
    audio_data: bytes = b""
    transcript: TranscriptResult | None = None
    transcript_text: str = ""
    summary: MeetingSummary | None = None
    actions: ActionResult | None = None
    insights: MeetingInsight | None = None
    followup: FollowUpResult | None = None
    errors: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())


# ============================================================
# 工厂函数
# ============================================================

def create_initial_state(
    meeting_id: str,
    audio_data: bytes = b"",
) -> dict[str, Any]:
    """
    创建 LangGraph 初始状态字典。

    LangGraph 使用普通 dict 作为 state，而不是 dataclass 实例，
    因此这里返回 dict 而不是 MeetingState 实例。
    """
    return {
        "meeting_id": meeting_id,
        "status": MeetingStatus.PENDING,
        "audio_data": audio_data,
        "transcript": None,
        "transcript_text": "",
        "summary": None,
        "actions": None,
        "insights": None,
        "followup": None,
        "errors": [],
        "created_at": datetime.now().isoformat(),
    }
