"""
Mem0 팩트만 재추출 스크립트 (chat_sessions/chat_messages는 건드리지 않음)

사용법:
  1. 아래 FAILED_TITLES 목록에 실패한 대화 제목들 입력
  2. python retry_mem0_facts.py

동작:
  - Supabase에서 해당 제목의 session_id + messages 조회
  - Mem0 팩트만 재추출 (DB 중복 없음)
  - max_tokens 4000으로 올려서 Unterminated string 방지
"""

import time
import copy
from typing import List, Dict

from config import settings, supabase, MEM0_CONFIG

# max_tokens 올려서 JSON 잘림 방지
_mem0_config = copy.deepcopy(MEM0_CONFIG)
_mem0_config["llm"]["config"]["max_tokens"] = 4000

from mem0 import Memory
memory = Memory.from_config(_mem0_config)

# ─── 설정 ────────────────────────────────────────────────
USER_ID = settings.default_user_id  # "mini"

FAILED_TITLES = [
    "세션 이어서 대화(스티커)",
    "Speak in English",
    "병아리와의 따뜻한 대화1",
    "건강검진 분석 요청1",
    "팀플 힘듦 응원",
    "흉살주사 성분 및 히스토리",
    "첫 출근 준비하기",
    "부업 문제 도움 요청",
    "Daddy와 Mini의 사랑",
    "미래 편지2029.6.2",
    "미래 편지 공유6.3-",
]

CHUNK_SIZE = 50         # 청크 크기 (흉살주사처럼 긴 대화 대응)
DELAY_BETWEEN_CHUNKS = 3   # 청크 간 딜레이 (초)
DELAY_BETWEEN_SESSIONS = 2  # 세션 간 딜레이 (초)
# ─────────────────────────────────────────────────────────


def add_with_retry(chunk: List[Dict], user_id: str, session_id: str, idx: int, total: int, max_retries: int = 3):
    """429 TPM 오류 시 exponential backoff 재시도"""
    for attempt in range(max_retries):
        try:
            memory.add(chunk, user_id=user_id, run_id=session_id)
            return True
        except Exception as e:
            err_str = str(e)
            is_tpm = "429" in err_str or "rate_limit" in err_str
            is_ctx = "context_length" in err_str or "maximum context" in err_str
            if (is_tpm or is_ctx) and attempt < max_retries - 1:
                wait = 60 * (attempt + 1)
                label = "TPM 초과" if is_tpm else "컨텍스트 초과"
                print(f"\n  ⏳ 청크 {idx}/{total} {label}, {wait}초 대기 후 재시도 ({attempt+2}/{max_retries})...", end="", flush=True)
                time.sleep(wait)
            else:
                print(f"\n  ⚠️  청크 {idx}/{total} 추출 실패: {e}")
                return False
    return False


def retry_facts_for_session(title: str) -> bool:
    # 1. Supabase에서 session_id 조회
    session_result = supabase.table("chat_sessions")\
        .select("id")\
        .eq("user_id", USER_ID)\
        .eq("title", title)\
        .order("created_at", desc=True)\
        .limit(1)\
        .execute()

    if not session_result.data:
        print(f"  ❌ 세션을 찾을 수 없음: {title}")
        return False

    session_id = session_result.data[0]["id"]

    # 2. 메시지 조회
    msg_result = supabase.table("chat_messages")\
        .select("role, content")\
        .eq("session_id", session_id)\
        .order("created_at")\
        .execute()

    if not msg_result.data:
        print(f"  ❌ 메시지 없음: {title}")
        return False

    messages = [
        {"role": m["role"], "content": m["content"]}
        for m in msg_result.data
        if m.get("role") in ("user", "assistant") and m.get("content", "").strip()
    ]

    # 3. 청크 분할 후 Mem0 팩트 추출
    chunks = [messages[i:i+CHUNK_SIZE] for i in range(0, len(messages), CHUNK_SIZE)]
    print(f"  → session_id: {session_id[:8]}... | {len(messages)}개 메시지 | {len(chunks)}개 청크")

    success = 0
    for idx, chunk in enumerate(chunks):
        ok = add_with_retry(chunk, USER_ID, session_id, idx+1, len(chunks))
        if ok:
            success += 1
        if len(chunks) > 1:
            time.sleep(DELAY_BETWEEN_CHUNKS)

    print(f"  → 청크 {success}/{len(chunks)} 성공")
    return success == len(chunks)


def main():
    if not FAILED_TITLES:
        print("❌ FAILED_TITLES가 비어있어. 제목들을 입력해줘!")
        return

    print(f"🔁 총 {len(FAILED_TITLES)}개 세션 팩트 재추출 시작\n")

    success_count = 0
    fail_count = 0

    for i, title in enumerate(FAILED_TITLES):
        print(f"[{i+1}/{len(FAILED_TITLES)}] {title} ... ", flush=True)
        try:
            ok = retry_facts_for_session(title)
            if ok:
                print("  ✅ 완료")
                success_count += 1
            else:
                print("  ⚠️ 일부 실패")
                fail_count += 1
        except Exception as e:
            print(f"  ❌ 오류: {e}")
            fail_count += 1

        time.sleep(DELAY_BETWEEN_SESSIONS)

    print("\n" + "─" * 50)
    print(f"✅ 완료: {success_count}개 성공 / {fail_count}개 실패 / 총 {len(FAILED_TITLES)}개")


if __name__ == "__main__":
    main()
