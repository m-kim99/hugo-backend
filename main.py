from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from openai import OpenAI
from typing import List, Dict, Optional

from config import settings
from memory_service import memory
from session_service import SessionService

app = FastAPI(title=settings.api_title)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

openai_client = OpenAI(api_key=settings.openai_api_key)

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
            # 새 세션 생성
            session = SessionService.create_session(req.user_id, req.message)
            session_id = session['id']
        
        # 사용자 메시지 저장
        SessionService.add_message(session_id, 'user', req.message)
        
        # 관련 메모리 검색 (run_id로 세션 지정)
        relevant_memories = memory.search(
            query=req.message, 
            user_id=req.user_id, 
            limit=5
        )
        memories_list = relevant_memories.get("results", [])
        memories_str = "\n".join(f"- {entry['memory']}" for entry in memories_list)
        
        # 시스템 프롬프트 구성
        if req.system_prompt:
            system_prompt = req.system_prompt.replace("{memories}", memories_str)
        else:
            system_prompt = settings.system_prompt_template.replace("{memories}", memories_str)
        
        # OpenAI API 호출
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": req.message}
        ]
        
        completion = openai_client.chat.completions.create(
            model=req.model,
            messages=messages,
            temperature=req.temperature
        )
        
        assistant_response = completion.choices[0].message.content
        
        # AI 응답 저장
        SessionService.add_message(session_id, 'assistant', assistant_response)
        
        # 대화 메모리에 추가 (run_id로 세션 연결)
        messages.append({"role": "assistant", "content": assistant_response})
        memory.add(messages, user_id=req.user_id, run_id=session_id)
        
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=settings.port)
