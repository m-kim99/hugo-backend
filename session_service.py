from typing import List, Optional, Dict
from config import supabase

# 슬라이딩 윈도우 설정
# gpt-4o-mini 128k 한도에서 시스템프롬프트/메모리/현재메시지 여유분 제외
MAX_HISTORY_TOKENS = 100_000

def estimate_tokens(text: str) -> int:
    """토큰 수 추정. 한글은 글자당 ~2토큰, 영어는 단어당 ~1.3토큰.
    정확도보다 안전한 과추정 방식 사용 (글자당 2토큰 고정).
    """
    return len(text) * 2

class SessionService:
    @staticmethod
    def create_session(user_id: str, first_message: str) -> Dict:
        """새 세션 생성"""
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
        result = supabase.table('chat_messages').insert({
            'session_id': session_id,
            'role': role,
            'content': content
        }).execute()
        supabase.rpc('increment_message_count', {'session_id': session_id}).execute()
        return result.data[0] if result.data else None

    @staticmethod
    def get_messages(session_id: str) -> List[Dict]:
        """세션의 전체 메시지 목록 조회 (프론트 렌더링용, limit 없음)"""
        result = supabase.table('chat_messages')\
            .select('*')\
            .eq('session_id', session_id)\
            .order('created_at')\
            .execute()
        return result.data

    @staticmethod
    def get_recent_messages(session_id: str) -> List[Dict]:
        """OpenAI 컨텍스트 조립용 슬라이딩 윈도우 메시지 조회.

        - 반드시 add_message(user) 호출 전에 실행 (현재 메시지 중복 방지)
        - 전체 메시지를 최신순으로 가져온 뒤 오래된 것부터 토큰 초과분 제거
        - MAX_HISTORY_TOKENS(100k) 안에서 최대한 많은 히스토리 유지
        - 리턴: [{"role": "user"|"assistant", "content": "..."}] 시간순
        """
        # 전체 메시지 최신순으로 가져오기 (DB limit 없음)
        result = supabase.table('chat_messages')\
            .select('role, content')\
            .eq('session_id', session_id)\
            .order('created_at', desc=True)\
            .execute()

        all_messages = result.data  # 최신순 정렬 상태

        # 최신 메시지부터 역순으로 토큰 누적, 한도 초과 시 중단 (슬라이딩 윈도우)
        selected = []
        total_tokens = 0
        for msg in all_messages:
            msg_tokens = estimate_tokens(msg['content'])
            if total_tokens + msg_tokens > MAX_HISTORY_TOKENS:
                break  # 오래된 것부터 자연스럽게 밀려남
            selected.append(msg)
            total_tokens += msg_tokens

        # 시간순(오래된 것부터)으로 뒤집어서 반환
        return list(reversed(selected))
