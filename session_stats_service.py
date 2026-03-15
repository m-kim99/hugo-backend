"""계층 3 확장: 세션 메타데이터 통계 서비스

패턴 참고: session_service.py (supabase 쿼리 방식 동일)

특징:
- 배치 아님 (실시간 조회)
- GPT 호출 없음
- 별도 테이블 없음 (기존 chat_sessions + chat_messages 활용)
- 매 요청마다 호출되므로 간단한 인메모리 캐싱 포함
"""

import time
from datetime import datetime, timedelta
from typing import Dict, Optional
from zoneinfo import ZoneInfo
from config import supabase

KST = ZoneInfo("Asia/Seoul")

# ─── 인메모리 캐시 (유저별, 1시간 유효) ─────────────────
_cache: Dict[str, Dict] = {}
CACHE_TTL = 3600  # 초


class SessionStatsService:
    """사용자 활동 통계 서비스

    계산 항목 (문서1 기준 17개 중 서버에서 가능한 5개):
    - 평균 대화 깊이 (세션당 메시지 수)
    - 평균 메시지 길이 (user 메시지 기준)
    - 활동 빈도 (1/7/30일)
    - 총 세션 수 + 계정 나이
    - 사용 모델 분포 (현재는 단일 모델이라 고정값)
    """

    @staticmethod
    def get_stats(user_id: str) -> Dict:
        """사용자 통계 조회 (캐시 적용)

        캐시 히트: 즉시 반환 (DB 쿼리 0회)
        캐시 미스: DB 쿼리 3회 → 캐시 저장 → 반환
        """
        now = time.time()
        cached = _cache.get(user_id)
        if cached and (now - cached.get("_ts", 0)) < CACHE_TTL:
            return cached

        stats = SessionStatsService._compute_stats(user_id)
        stats["_ts"] = now
        _cache[user_id] = stats
        return stats

    @staticmethod
    def _compute_stats(user_id: str) -> Dict:
        """실제 통계 계산 (DB 쿼리)"""

        # 1. 세션 통계: 총 수, 최초 생성일, 평균 메시지 수
        sessions_result = supabase.table('chat_sessions')\
            .select('created_at, message_count')\
            .eq('user_id', user_id)\
            .order('created_at')\
            .execute()

        sessions = sessions_result.data or []
        total_sessions = len(sessions)

        if total_sessions == 0:
            return {
                "avg_depth": 0,
                "avg_msg_length": 0,
                "active_1d": 0, "active_7d": 0, "active_30d": 0,
                "total_sessions": 0,
                "account_age_weeks": 0,
            }

        # 평균 대화 깊이
        msg_counts = [s.get("message_count", 0) for s in sessions]
        avg_depth = round(sum(msg_counts) / len(msg_counts), 1) if msg_counts else 0

        # 계정 나이 (주 단위)
        first_created = sessions[0].get("created_at", "")
        account_age_weeks = 0
        if first_created:
            try:
                first_dt = datetime.fromisoformat(first_created.replace("Z", "+00:00"))
                now_dt = datetime.now(KST)
                account_age_weeks = max(1, (now_dt - first_dt).days // 7)
            except (ValueError, TypeError):
                account_age_weeks = 0

        # 활동 빈도: 최근 1/7/30일 중 며칠 활동했는가
        now_dt = datetime.now(KST)
        active_dates = set()
        for s in sessions:
            try:
                dt = datetime.fromisoformat(s["created_at"].replace("Z", "+00:00"))
                active_dates.add(dt.date())
            except (ValueError, TypeError, KeyError):
                continue

        active_1d = 1 if now_dt.date() in active_dates else 0
        active_7d = sum(
            1 for d in active_dates
            if (now_dt.date() - d).days < 7
        )
        active_30d = sum(
            1 for d in active_dates
            if (now_dt.date() - d).days < 30
        )

        # 2. 평균 메시지 길이 (user 메시지만, 최근 100개 샘플)
        msg_result = supabase.table('chat_messages')\
            .select('content')\
            .eq('role', 'user')\
            .order('created_at', desc=True)\
            .limit(100)\
            .execute()

        user_msgs = msg_result.data or []
        if user_msgs:
            lengths = [len(m.get("content", "")) for m in user_msgs]
            avg_msg_length = round(sum(lengths) / len(lengths), 1)
        else:
            avg_msg_length = 0

        return {
            "avg_depth": avg_depth,
            "avg_msg_length": avg_msg_length,
            "active_1d": active_1d,
            "active_7d": active_7d,
            "active_30d": active_30d,
            "total_sessions": total_sessions,
            "account_age_weeks": account_age_weeks,
        }

    @staticmethod
    def format_for_metadata(stats: Dict) -> str:
        """build_session_metadata()에 추가할 문자열 생성

        문서1 형식:
        [사용자 활동 통계]
        자동 생성됨. 사용 패턴을 반영하지만, 부정확할 수 있음.
        - 사용자의 평균 대화 깊이는 3.2입니다.
        ...
        """
        if stats.get("total_sessions", 0) == 0:
            return ""

        lines = [
            "[사용자 활동 통계]",
            "자동 생성됨. 사용 패턴을 반영하지만, 부정확할 수 있음.",
            f"- 사용자의 평균 대화 깊이는 {stats['avg_depth']}입니다.",
            f"- 사용자의 평균 메시지 길이는 {stats['avg_msg_length']}자입니다.",
            f"- 사용자는 최근 1일 중 {stats['active_1d']}일, "
            f"7일 중 {stats['active_7d']}일, "
            f"30일 중 {stats['active_30d']}일 활동했습니다.",
            f"- 사용자는 총 {stats['total_sessions']}개의 대화를 나눴으며, "
            f"계정 생성 후 {stats['account_age_weeks']}주입니다.",
        ]

        return "\n".join(lines)
