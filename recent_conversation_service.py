"""계층 9: Recent Conversation Content 서비스

패턴 참고: session_service.py
- supabase 쿼리 방식 동일 (get_sessions, chat_messages 조회)
- 차이: 현재 세션 제외, user 메시지만, 크로스 세션

특징 (다른 계층과 다름):
- 배치 스크립트 없음 (실시간 조회)
- GPT 호출 없음 (포맷팅만)
- 별도 테이블 없음 (기존 chat_sessions + chat_messages 활용)
- 매 /chat 요청마다 호출
"""

from datetime import datetime
from typing import List, Dict, Optional
from config import supabase


class RecentConversationService:
    """최근 크로스 세션 대화 콘텐츠 서비스

    - 현재 세션을 제외한 최근 ~40개 세션의 user 메시지를 조회
    - 문서1 형식으로 포맷팅하여 시스템 프롬프트에 주입
    - 매 요청마다 실시간 호출 (배치 아님)
    """

    @staticmethod
    def get_recent_cross_session(
        user_id: str,
        current_session_id: Optional[str] = None,
        session_limit: int = 40,
        msgs_per_session: int = 5,
    ) -> List[Dict]:
        """현재 세션 제외, 최근 세션들의 user 메시지 조회

        SessionService.get_sessions() + get_messages() 패턴 조합.

        반환 형식:
        [
          {
            "session_title": "일본 여행 일정",
            "created_at": "2025-05-04T17:19:00+09:00",
            "user_messages": ["일본 3박4일 짜줘", "오사카 맛집 추천해줘"]
          },
          ...
        ]
        """
        # 1. 최근 세션 조회 (현재 세션 제외)
        query = supabase.table('chat_sessions')\
            .select('id, title, created_at')\
            .eq('user_id', user_id)\
            .order('created_at', desc=True)\
            .limit(session_limit + 1)  # 현재 세션 제외 여유분

        result = query.execute()
        sessions = result.data or []

        # 현재 세션 제외
        if current_session_id:
            sessions = [s for s in sessions if s['id'] != current_session_id]

        sessions = sessions[:session_limit]

        if not sessions:
            return []

        # 2. 각 세션에서 user 메시지만 추출
        entries = []
        for session in sessions:
            msg_result = supabase.table('chat_messages')\
                .select('content')\
                .eq('session_id', session['id'])\
                .eq('role', 'user')\
                .order('created_at')\
                .limit(msgs_per_session)\
                .execute()

            user_msgs = [
                m['content'][:150]  # 메시지당 최대 150자 (토큰 절약)
                for m in (msg_result.data or [])
                if m.get('content', '').strip()
            ]

            if user_msgs:
                entries.append({
                    'session_title': session.get('title', '제목 없음'),
                    'created_at': session.get('created_at', ''),
                    'user_messages': user_msgs,
                })

        return entries

    @staticmethod
    def format_for_prompt(entries: List[Dict]) -> str:
        """시스템 프롬프트 주입용 문자열 생성

        문서1 형식 (Rehberger 추출):
        1. 0504T17:19 New Conversation:||||hello||||show me a high five!
        2. 0504T17:18 Emoji Fire:||||show me the fire emoji
        ...
        10. 0503T21 Seattle Weather:||||how's the weather in seattle?

        타임스탬프 규칙:
        - 최근 5개: 분 단위 (MMDDThh:mm)
        - 6번 이후: 시간 단위 (MMDDThh)
        """
        if not entries:
            return "최근 다른 대화 기록이 없습니다."

        lines = []
        for i, entry in enumerate(entries, 1):
            # 타임스탬프 포맷팅
            ts = _format_timestamp(entry.get('created_at', ''), precise=(i <= 5))
            title = entry.get('session_title', '제목 없음')

            # user 메시지를 |||| 구분자로 연결
            msgs = "||||".join(entry.get('user_messages', []))

            lines.append(f"{i}. {ts} {title}:||||{msgs}")

        return "\n".join(lines)


def _format_timestamp(iso_str: str, precise: bool = True) -> str:
    """ISO 타임스탬프를 문서1 형식으로 변환

    precise=True:  0504T17:19 (분 단위, 최근 5개)
    precise=False: 0503T21    (시간 단위, 6번 이후)
    """
    if not iso_str:
        return "0000T00"

    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        if precise:
            return dt.strftime("%m%dT%H:%M")
        else:
            return dt.strftime("%m%dT%H")
    except (ValueError, TypeError):
        return "0000T00"
