@echo off
chcp 65001 > nul

:: 1. 백엔드(FastAPI) 서버를 새 명령 프롬프트 창에서 실행합니다.
:: 메인 앱 기동 시 lifespan 이벤트를 통해 비동기 워커와 스케줄러가 자동으로 함께 실행됩니다.
start "NexusMon Backend" cmd /c "cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000"

:: 2. 프론트엔드(Vue 3) 개발 서버를 새 명령 프롬프트 창에서 실행합니다.
:: 실행 완료 후 브라우저에서 http://localhost:5173 으로 접속 가능합니다.
start "NexusMon Frontend" cmd /c "cd frontend && npm run dev"

:: 3. 에이전트 수집 데몬을 새 명령 프롬프트 창에서 실행합니다.
:: 백엔드 API 서버가 완전히 기동되어 포트가 열릴 수 있도록 5초 대기 후 실행합니다.
start "NexusMon Agent" cmd /c "timeout /t 5 /nobreak && python agent\agent.py"

echo 모든 서비스(백엔드, 프론트엔드, 에이전트)가 각각 별도의 창에서 실행되었습니다.
echo 각 창을 닫으면 해당 서비스가 종료됩니다.
pause
