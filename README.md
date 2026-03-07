# Hugo Memory Chat - Backend

Mini와 Hugo의 메모리 챗봇 백엔드 (FastAPI + Mem0 + Supabase pgvector)

## 기술 스택
- **FastAPI**: 백엔드 프레임워크
- **Mem0**: Self-hosted 메모리 시스템
- **Supabase**: PostgreSQL + pgvector
- **OpenAI**: GPT-4o-mini + text-embedding-3-small

## 환경 설정

1. Python 가상환경 생성:
```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
```

2. 패키지 설치:
```bash
pip install -r requirements.txt
```

3. 환경변수 설정:
```bash
cp .env.example .env
# .env 파일 수정:
# - SUPABASE_* : Supabase 정보
# - OPENAI_API_KEY : OpenAI API 키
# - SYSTEM_PROMPT_TEMPLATE : Hugo의 시스템 프롬프트 (커스터마이징 가능)
# - DEFAULT_USER_ID : 기본 사용자 ID
# - AVAILABLE_MODELS : 사용 가능한 모델 목록 (쉼표 구분)
```

4. 로컬 실행:
```bash
python main.py
# 또는
uvicorn main:app --reload
```

## API 엔드포인트

### POST /chat
대화 + 메모리 저장

**Request:**
```json
{
  "message": "오늘 뭐했어?",
  "user_id": "mini",
  "model": "gpt-4o-mini",
  "temperature": 0.8
}
```

**Response:**
```json
{
  "response": "Hugo의 응답",
  "memories": [...]
}
```

### GET /memories?user_id=mini
모든 메모리 조회

### DELETE /memories/{memory_id}
특정 메모리 삭제

### GET /models
사용 가능한 모델 목록

## 배포 (Railway)

1. Railway 프로젝트 생성
2. GitHub 연결
3. 환경변수 설정
4. 자동 배포

## 주의사항

- `port`는 문자열로 변환 필요 (pgvector 요구사항)
- Supabase pgvector extension 활성화 필수
- OpenAI API 키 필수
