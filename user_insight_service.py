"""계층 7: Helpful User Insights 서비스

패턴 참고: response_preference_service.py
- supabase 쿼리 방식 동일
- format_for_prompt: 1문장 사실 + Confidence=high (근거 없음)
"""

from typing import List, Dict
from config import supabase


class UserInsightService:
    """사용자 인사이트 관리 서비스

    - 배치 스크립트(generate_user_insights.py)가 주기적으로 생성
    - 매 요청마다 전체가 시스템 프롬프트에 포함됨
    - 최대 14개 항목 (문서1 기준)
    """

    @staticmethod
    def get_insights(user_id: str, limit: int = 14) -> List[Dict]:
        """사용자 인사이트 조회 (생성 순)"""
        result = supabase.table('user_insights')\
            .select('*')\
            .eq('user_id', user_id)\
            .order('created_at')\
            .limit(limit)\
            .execute()

        return result.data

    @staticmethod
    def replace_all(user_id: str, insights: List[Dict]) -> int:
        """기존 인사이트 전체 교체 (배치 스크립트용)"""
        supabase.table('user_insights')\
            .delete()\
            .eq('user_id', user_id)\
            .execute()

        if not insights:
            return 0

        rows = []
        for ins in insights:
            rows.append({
                'user_id': user_id,
                'insight': ins['insight'],
                'confidence': ins.get('confidence', 'high'),
                'category': ins.get('category', ''),
            })

        result = supabase.table('user_insights')\
            .insert(rows)\
            .execute()

        return len(result.data) if result.data else 0

    @staticmethod
    def format_for_prompt(insights: List[Dict]) -> str:
        """시스템 프롬프트 주입용 문자열 생성

        문서1의 실제 형식 (계층 5·6과 다름 주의):
        1. 사용자 이름은 Johann입니다. Confidence=high
        2. 사용자는 시애틀에 거주합니다. Confidence=high
        → 근거 없음, 1문장만, 평문 Confidence
        """
        if not insights:
            return "아직 충분한 대화 기록이 없습니다."

        lines = []
        for i, ins in enumerate(insights, 1):
            lines.append(
                f"{i}. {ins['insight']} Confidence={ins.get('confidence', 'high')}"
            )

        return "\n".join(lines)
