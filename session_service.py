from uuid import UUID
from datetime import datetime
from typing import List, Optional, Dict
from config import supabase

class SessionService:
    @staticmethod
    def create_session(user_id: str, first_message: str) -> Dict:
        """새 세션 생성"""
        # 첫 메시지로 제목 생성 (최대 50자)
        title = first_message[:50] + "..." if len(first_message) > 50 else first_message
        
        result = supabase.table('chat_sessions').insert({
            'user_id': user_id,
            'title': title,
            'message_count': 0
        }).execute()
        
        return result.data[0] if result.data else None
    
    @staticmethod
    def get_sessions(user_id: str, limit: int = 50) -> List[Dict]:
        """사용자의 세션 목록 조회"""
        result = supabase.table('chat_sessions')\
            .select('*')\
            .eq('user_id', user_id)\
            .order('updated_at', desc=True)\
            .limit(limit)\
            .execute()
        
        return result.data
    
    @staticmethod
    def get_session(session_id: str) -> Optional[Dict]:
        """특정 세션 조회"""
        result = supabase.table('chat_sessions')\
            .select('*')\
            .eq('id', session_id)\
            .single()\
            .execute()
        
        return result.data
    
    @staticmethod
    def delete_session(session_id: str) -> bool:
        """세션 삭제 (메시지도 CASCADE로 삭제됨)"""
        supabase.table('chat_sessions')\
            .delete()\
            .eq('id', session_id)\
            .execute()
        
        return True
    
    @staticmethod
    def add_message(session_id: str, role: str, content: str) -> Dict:
        """메시지 추가"""
        # 메시지 저장
        result = supabase.table('chat_messages').insert({
            'session_id': session_id,
            'role': role,
            'content': content
        }).execute()
        
        # 세션의 message_count 증가
        supabase.rpc('increment_message_count', {'session_id': session_id}).execute()
        
        return result.data[0] if result.data else None
    
    @staticmethod
    def get_messages(session_id: str) -> List[Dict]:
        """세션의 메시지 목록 조회"""
        result = supabase.table('chat_messages')\
            .select('*')\
            .eq('session_id', session_id)\
            .order('created_at')\
            .execute()
        
        return result.data
