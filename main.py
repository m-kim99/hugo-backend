from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from openai import OpenAI
from typing import List, Dict, Optional
from datetime import datetime
from zoneinfo import ZoneInfo

from config import settings
from memory_service import memory
from session_service import SessionService
from explicit_memory_service import ExplicitMemoryService

app = FastAPI(title=settings.api_title)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

openai_client = OpenAI(api_key=settings.openai_api_key)

KST = ZoneInfo("Asia/Seoul")
WEEKDAYS_KO = ["월요일", "화요일", "수요일", "목요일", "금요일", "토요일", "일요일"]

def build_session_metadata() -> str:
    """[2] Session Metadata: 현재 KST 기준 날짜/시간/요일 생성."""
    now = datetime.now(KST)
    weekday = WEEKDAYS_KO[now.weekday()]
    return (
        f"[현재 세션 정보]\n"
        f"- 날짜: {now.strftime('%Y년 %m월 %d일')} ({weekday})\n"
        f"- 시각: {now.strftime('%H시 %M분')}\n"
    )


class ChatRequest(BaseModel):
    message: str
    user_id: str = settings.default_user_id
    session_id: Optional[str] = None
    model: str = "gpt-4o-mini"
    temperature: float = 0.8
    system_prompt: str | None = None

class ChatResponse(BaseModel):
    response: str
    memories: List[Dict]
    session_id: str

@app.get("/")
async def root():
    return {"status": "running"}

@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    try:
        # 세션 처리
        session_id = req.session_id
        if not session_id:
            session = SessionService.create_session(req.user_id, req.message)
            session_id = session['id']

        # [5] 히스토리 조회 — 반드시 add_message(user) 호출 전에 실행
        history = SessionService.get_recent_messages(session_id)

        # 사용자 메시지 DB 저장
        SessionService.add_message(session_id, 'user', req.message)

        # [4A] 명시적 메모리 조회 (항상 전체 포함)
        explicit_memories = ExplicitMemoryService.get_all(req.user_id)
        explicit_str = "\n".join(f"- {mem['content']}" for mem in explicit_memories)

        # [4B] 동적 메모리 검색 (벡터 검색, 관련있는 것만)
        relevant_memories = memory.search(
            query=req.message,
            user_id=req.user_id,
            limit=5
        )
        memories_list = relevant_memories.get("results", [])
        dynamic_str = "\n".join(f"- {entry['memory']}" for entry in memories_list)

        # [3] 통합 시스템 프롬프트 구성
        if req.system_prompt:
            base_prompt = req.system_prompt
        else:
            base_prompt = settings.system_prompt_template

        if explicit_str:
            base_prompt = base_prompt.replace(
                "{memories}",
                f"[항상 기억하는 것들]\n{explicit_str}\n\n[대화 맥락 관련 기억]\n{dynamic_str}"
            )
        else:
            base_prompt = base_prompt.replace("{memories}", dynamic_str)

        # [2] Session Metadata를 system prompt 앞에 주입
        session_metadata = build_session_metadata()
        system_prompt = session_metadata + "\n" + base_prompt

        # OpenAI messages 조립: 시스템 + [5]히스토리 + 현재 메시지
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(history)
        messages.append({"role": "user", "content": req.message})

        completion = openai_client.chat.completions.create(
            model=req.model,
            messages=messages,
            temperature=req.temperature
        )

        assistant_response = completion.choices[0].message.content

        # AI 응답 DB 저장
        SessionService.add_message(session_id, 'assistant', assistant_response)

        # 메모리에는 현재 교환만 추가 (히스토리 전체 넘기면 중복 팩트 추출됨)
        memory.add(
            [
                {"role": "user", "content": req.message},
                {"role": "assistant", "content": assistant_response}
            ],
            user_id=req.user_id,
            run_id=session_id
        )

        return ChatResponse(
            response=assistant_response,
            memories=memories_list,
            session_id=session_id
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# 세션 관련 엔드포인트
@app.post("/sessions")
async def create_session(user_id: str = settings.default_user_id, title: str = "새 대화"):
    try:
        session = SessionService.create_session(user_id, title)
        return session
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/sessions")
async def get_sessions(user_id: str = settings.default_user_id, limit: int = 50):
    try:
        sessions = SessionService.get_sessions(user_id, limit)
        return {"sessions": sessions}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/sessions/{session_id}")
async def get_session(session_id: str):
    try:
        session = SessionService.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        return session
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/sessions/{session_id}/messages")
async def get_session_messages(session_id: str):
    try:
        messages = SessionService.get_messages(session_id)
        return {"messages": messages}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    try:
        SessionService.delete_session(session_id)
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# 기존 엔드포인트들
@app.get("/memories")
async def get_all_memories(user_id: str = settings.default_user_id):
    try:
        return {"memories": memory.get_all(user_id=user_id)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/memories/{memory_id}")
async def delete_memory(memory_id: str):
    try:
        memory.delete(memory_id)
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/models")
async def get_models():
    return {"models": settings.available_models.split(",")}

# 명시적 메모리 엔드포인트
@app.get("/explicit-memories")
async def get_explicit_memories(user_id: str = settings.default_user_id):
    try:
        memories = ExplicitMemoryService.get_all(user_id)
        return {"memories": memories}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/explicit-memories")
async def add_explicit_memory(
    user_id: str = settings.default_user_id,
    content: str = "",
    category: str | None = None,
    priority: int = 0
):
    try:
        if not content.strip():
            raise HTTPException(status_code=400, detail="content는 필수입니다")
        mem_result = ExplicitMemoryService.add(user_id, content.strip(), category, priority)
        return mem_result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/explicit-memories/{memory_id}")
async def update_explicit_memory(
    memory_id: str,
    content: str | None = None,
    category: str | None = None,
    priority: int | None = None
):
    try:
        mem_result = ExplicitMemoryService.update(memory_id, content, category, priority)
        if not mem_result:
            raise HTTPException(status_code=404, detail="메모리를 찾을 수 없습니다")
        return mem_result
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/explicit-memories/{memory_id}")
async def delete_explicit_memory(memory_id: str):
    try:
        ExplicitMemoryService.delete(memory_id)
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=settings.port)
