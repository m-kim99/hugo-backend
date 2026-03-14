from datetime import datetime
from typing import List, Optional, Dict
from config import supabase

class SessionService:
    @staticmethod
    def create_session(user_id: str, first_message: str) -> Dict:
        title = first_message[:50] + "..." if len(first_message) > 50 else first_message
        result = supabase.table('chat_sessions').insert({
            'user_id': user_id,
            'title': title,
            'message_count': 0
        }).execute()
        return result.data[0] if result.data else None

    @staticmethod
    def get_sessions(user_id: str, limit: int = 50, offset: int = 0) -> List[Dict]:
        result = supabase.table('chat_sessions')\
            .select('*')\
            .eq('user_id', user_id)\
            .order('updated_at', desc=True)\
            .range(offset, offset + limit - 1)\
            .execute()
        return result.data

    @staticmethod
    def get_session(session_id: str) -> Optional[Dict]:
        result = supabase.table('chat_sessions')\
            .select('*')\
            .eq('id', session_id)\
            .single()\
            .execute()
        return result.data

    @staticmethod
    def delete_session(session_id: str) -> bool:
        supabase.table('chat_sessions')\
            .delete()\
            .eq('id', session_id)\
            .execute()
        return True

    @staticmethod
    def add_message(session_id: str, role: str, content: str) -> Dict:
        result = supabase.table('chat_messages').insert({
            'session_id': session_id,
            'role': role,
            'content': content
        }).execute()
        supabase.rpc('increment_message_count', {'session_id': session_id}).execute()
        return result.data[0] if result.data else None

    @staticmethod
    def get_messages(session_id: str) -> List[Dict]:
        result = supabase.table('chat_messages')\
            .select('*')\
            .eq('session_id', session_id)\
            .order('created_at')\
            .execute()
        return result.data

    @staticmethod
    def get_recent_messages(session_id: str, limit: int = 20) -> List[Dict]:
        """OpenAI 컨텍스트 조립용 최근 메시지 조회.

        반드시 현재 유저 메시지를 add_message()로 저장하기 전에 호출해야
        현재 메시지가 히스토리에 중복 포함되는 것을 방지할 수 있음.
        """
        result = supabase.table('chat_messages')\
            .select('role, content')\
            .eq('session_id', session_id)\
            .order('created_at', desc=True)\
            .limit(limit)\
            .execute()
        return list(reversed(result.data))

    @staticmethod
    def search_messages(user_id: str, query: str, limit: int = 20) -> List[Dict]:
        """키워드로 메시지 전문 검색.

        chat_messages.content ILIKE '%query%' 로 검색 후
        session title, message_id, snippet 반환.
        user_id 필터는 Python 레벨에서 수행 (PostgREST 조인 필터 호환성).
        """
        if not query.strip():
            return []

        result = supabase.table('chat_messages')\
            .select('id, content, role, session_id, chat_sessions!inner(title, updated_at, user_id)')\
            .ilike('content', f'%{query}%')\
            .order('created_at', desc=True)\
            .limit(limit * 3)\
            .execute()

        # user_id 필터 + 중복 session 제거 (session당 첫 번째 매칭 메시지만)
        seen_sessions = set()
        results = []
        for row in result.data:
            session_info = row.get('chat_sessions') or {}
            if session_info.get('user_id') != user_id:
                continue
            session_id = row['session_id']
            if session_id in seen_sessions:
                continue
            seen_sessions.add(session_id)

            # 키워드 주변 스니펫 생성
            content = row['content']
            idx = content.lower().find(query.lower())
            if idx == -1:
                snippet = content[:100]
            else:
                start = max(0, idx - 40)
                end = min(len(content), idx + len(query) + 40)
                snippet = ('...' if start > 0 else '') + content[start:end] + ('...' if end < len(content) else '')

            results.append({
                'message_id': row['id'],
                'session_id': session_id,
                'session_title': session_info.get('title', '제목 없음'),
                'session_updated_at': session_info.get('updated_at', ''),
                'role': row['role'],
                'snippet': snippet,
            })

            if len(results) >= limit:
                break

        return results
