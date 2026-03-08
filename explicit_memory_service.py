from typing import List, Dict, Optional
from config import supabase

class ExplicitMemoryService:
    """명시적 메모리(장기 메모리) 관리 서비스
    
    - 사용자가 직접 추가/관리하는 고정 메모리
    - 매 요청마다 전체가 시스템 프롬프트에 포함됨
    - 우선순위(priority) 순으로 정렬
    """
    
    @staticmethod
    def get_all(user_id: str) -> List[Dict]:
        """사용자의 모든 명시적 메모리 조회 (우선순위 순)"""
        result = supabase.table('explicit_memories')\
            .select('*')\
            .eq('user_id', user_id)\
            .order('priority', desc=True)\
            .order('created_at')\
            .execute()
        
        return result.data
    
    @staticmethod
    def add(
        user_id: str, 
        content: str, 
        category: Optional[str] = None, 
        priority: int = 0
    ) -> Dict:
        """명시적 메모리 추가"""
        result = supabase.table('explicit_memories').insert({
            'user_id': user_id,
            'content': content,
            'category': category,
            'priority': priority
        }).execute()
        
        return result.data[0] if result.data else None
    
    @staticmethod
    def update(
        memory_id: str, 
        content: Optional[str] = None, 
        category: Optional[str] = None,
        priority: Optional[int] = None
    ) -> Dict:
        """메모리 수정"""
        update_data = {}
        if content is not None:
            update_data['content'] = content
        if category is not None:
            update_data['category'] = category
        if priority is not None:
            update_data['priority'] = priority
        
        if not update_data:
            raise ValueError("업데이트할 필드가 없습니다")
        
        result = supabase.table('explicit_memories')\
            .update(update_data)\
            .eq('id', memory_id)\
            .execute()
        
        return result.data[0] if result.data else None
    
    @staticmethod
    def delete(memory_id: str) -> bool:
        """메모리 삭제"""
        supabase.table('explicit_memories')\
            .delete()\
            .eq('id', memory_id)\
            .execute()
        
        return True
