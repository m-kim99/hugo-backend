"""계층 5: Assistant Response Preferences 서비스

패턴 참고: topic_highlight_service.py
- supabase 테이블 쿼리 방식 동일
- get_highlights → get_preferences로 이름 변경
- format_for_prompt: 문서1 형식 (선호도 + 근거 + Confidence=high)
"""

from typing import List, Dict
from config import supabase


class ResponsePreferenceService:
    """응답 선호도 관리 서비스

    - 배치 스크립트(generate_response_preferences.py)가 주기적으로 생성
    - 매 요청마다 전체가 시스템 프롬프트에 포함됨
    - 최대 15개 항목 (문서1 기준)
    """

    @staticmethod
    def get_preferences(user_id: str, limit: int = 15) -> List[Dict]:
        """사용자의 응답 선호도 조회 (생성 순)

        TopicHighlightService.get_highlights()와 동일한 패턴.
        """
        result = supabase.table('response_preferences')\
            .select('*')\
            .eq('user_id', user_id)\
            .order('created_at')\
            .limit(limit)\
            .execute()

        return result.data

    @staticmethod
    def replace_all(user_id: str, preferences: List[Dict]) -> int:
        """기존 선호도 전체 교체 (배치 스크립트용)

        TopicHighlightService.replace_all()과 동일한 패턴.
        """
        # 기존 삭제
        supabase.table('response_preferences')\
            .delete()\
            .eq('user_id', user_id)\
            .execute()

        if not preferences:
            return 0

        # 새로 삽입
        rows = []
        for p in preferences:
            rows.append({
                'user_id': user_id,
                'preference': p['preference'],
                'evidence': p.get('evidence', ''),
                'confidence': p.get('confidence', 'high'),
                'category': p.get('category', ''),
            })

        result = supabase.table('response_preferences')\
            .insert(rows)\
            .execute()

        return len(result.data) if result.data else 0

    @staticmethod
    def format_for_prompt(preferences: List[Dict]) -> str:
        """시스템 프롬프트 주입용 문자열 생성

        문서1의 실제 형식 (계층 6과 다름 주의):
        1. 사용자는 응답이 구조화된 형식을 따르기를 선호합니다...
           여러 상호작용에서 사용자는 특히 상세한 설명이나...
           Confidence=high            ← 공백 없음, 굵게 아님
        """
        if not preferences:
            return "아직 충분한 대화 기록이 없습니다."

        lines = []
        for i, p in enumerate(preferences, 1):
            block = f"{i}. {p['preference']}"
            if p.get('evidence'):
                block += f"\n   {p['evidence']}"
            block += f"\n   Confidence={p.get('confidence', 'high')}"
            lines.append(block)

        return "\n\n".join(lines)
