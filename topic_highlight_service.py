"""계층 6: Notable Past Conversation Topic Highlights 서비스

패턴 참고: explicit_memory_service.py
- supabase 테이블 쿼리 방식 동일
- get_all → get_highlights로 이름만 변경
- 매 요청마다 전체가 시스템 프롬프트에 포함됨 (최대 8개)
"""

from typing import List, Dict
from config import supabase


class TopicHighlightService:
    """주요 대화 주제 하이라이트 관리 서비스

    - 배치 스크립트(generate_topic_highlights.py)가 주기적으로 생성
    - 매 요청마다 전체가 시스템 프롬프트에 포함됨
    - 최대 8개 항목 (문서1 기준)
    """

    @staticmethod
    def get_highlights(user_id: str, limit: int = 8) -> List[Dict]:
        """사용자의 주제 하이라이트 조회 (시간순)

        ExplicitMemoryService.get_all()과 동일한 패턴.
        """
        result = supabase.table('topic_highlights')\
            .select('*')\
            .eq('user_id', user_id)\
            .order('created_at')\
            .limit(limit)\
            .execute()

        return result.data

    @staticmethod
    def replace_all(user_id: str, highlights: List[Dict]) -> int:
        """기존 하이라이트 전체 교체 (배치 스크립트용)

        배치 실행 시 기존 데이터 삭제 후 새로 삽입.
        """
        # 기존 삭제
        supabase.table('topic_highlights')\
            .delete()\
            .eq('user_id', user_id)\
            .execute()

        if not highlights:
            return 0

        # 새로 삽입
        rows = []
        for h in highlights:
            rows.append({
                'user_id': user_id,
                'period': h['period'],
                'summary': h['summary'],
                'confidence': h.get('confidence', 'high'),
                'session_count': h.get('session_count', 0),
            })

        result = supabase.table('topic_highlights')\
            .insert(rows)\
            .execute()

        return len(result.data) if result.data else 0

    @staticmethod
    def format_for_prompt(highlights: List[Dict]) -> str:
        """시스템 프롬프트 주입용 문자열 생성

        문서1의 실제 형식:
        1. 2024년 초, 사용자는 ... 했습니다.
           사용자는 ... 평가합니다.
           **Confidence = high**
        """
        if not highlights:
            return "아직 충분한 대화 기록이 없습니다."

        lines = []
        for i, h in enumerate(highlights, 1):
            lines.append(
                f"{i}. {h['summary']}\n"
                f"   **Confidence = {h.get('confidence', 'high')}**"
            )

        return "\n\n".join(lines)
