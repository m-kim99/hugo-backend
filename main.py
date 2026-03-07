from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from openai import OpenAI
from typing import List, Dict

from config import settings
from memory_service import memory

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
    model: str = "gpt-4o-mini"
    temperature: float = 0.8
    system_prompt: str | None = None

class ChatResponse(BaseModel):
    response: str
    memories: List[Dict]

@app.get("/")
async def root():
    return {"status": "running"}

@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    try:
        # 관련 메모리 검색
        relevant_memories = memory.search(query=req.message, user_id=req.user_id, limit=5)
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
        
        # 대화 메모리에 추가
        messages.append({"role": "assistant", "content": assistant_response})
        memory.add(messages, user_id=req.user_id)
        
        return ChatResponse(response=assistant_response, memories=memories_list)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

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
