"""계층 8: User Knowledge Memories 서비스

패턴 참고: user_insight_service.py
- supabase 쿼리 방식 동일
- format_for_prompt: 번호 없는 단락 나열 (문서1 형식)
  → "당신은 열렬한 여행자이자 계획가로..." 식의 2인칭 서술
"""

from typing import List, Dict
from config import supabase


class UserKnowledgeMemoryService:
    """유저 지식 메모리 관리 서비스

    - 배치 스크립트(generate_user_knowledge_memories.py)가 주기적으로 생성
    - 계층 6·7의 출력을 합성 입력으로 사용하는 메타 계층
    - 매 요청마다 전체가 시스템 프롬프트에 포함됨
    - 최대 10개 단락 (문서1 기준)
    """

    @staticmethod
    def get_memories(user_id: str, limit: int = 10) -> List[Dict]:
        """유저 지식 메모리 조회 (paragraph_order 순)"""
        result = supabase.table('user_knowledge_memories')\
            .select('*')\
            .eq('user_id', user_id)\
            .order('paragraph_order')\
            .limit(limit)\
            .execute()

        return result.data

    @staticmethod
    def replace_all(user_id: str, paragraphs: List[Dict]) -> int:
        """기존 메모리 전체 교체 (배치 스크립트용)"""
        supabase.table('user_knowledge_memories')\
            .delete()\
            .eq('user_id', user_id)\
            .execute()

        if not paragraphs:
            return 0

        rows = []
        for i, p in enumerate(paragraphs):
            rows.append({
                'user_id': user_id,
                'paragraph': p['paragraph'],
                'section': p.get('section', ''),
                'paragraph_order': i,
            })

        result = supabase.table('user_knowledge_memories')\
            .insert(rows)\
            .execute()

        return len(result.data) if result.data else 0

    @staticmethod
    def format_for_prompt(memories: List[Dict]) -> str:
        """시스템 프롬프트 주입용 문자열 생성

        문서1 형식: 번호 없는 단락 나열, 2인칭 서술.
        단락 사이에 빈 줄 하나.
        """
        if not memories:
            return "아직 충분한 대화 기록이 없습니다."

        return "\n\n".join(m['paragraph'] for m in memories)
