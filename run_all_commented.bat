@echo off
chcp 65001 > nul

:: 1. 백엔드(FastAPI) 서버를 새 명령 프롬프트 창에서 실행합니다.
:: 1. 백엔드 API 서버 시작
:: uvicorn을 사용하여 FastAPI 애플리케이션을 실행합니다.
start "NexusMon Backend" cmd /c "cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000"

:: 1-1. 백엔드 백그라운드 워커 시작
:: 스케줄러와 알람 워커 등을 별도 프로세스로 실행합니다.
start "NexusMon Worker" cmd /c "cd backend && python -m app.worker_main"

:: 2. 프론트엔드 개발 서버 시작
:: Vite를 사용하여 Vue.js 애플리케이션을 실행합니다.
start "NexusMon Frontend" cmd /c "cd frontend && npm run dev"

:: 3. 에이전트 수집 데몬을 새 명령 프롬프트 창에서 실행합니다.
:: 백엔드 API 서버가 완전히 기동되어 포트가 열릴 수 있도록 5초 대기 후 실행합니다.
start "NexusMon Agent" cmd /c "timeout /t 5 /nobreak && python agent\agent.py"

echo 모든 서비스(백엔드, 프론트엔드, 에이전트)가 각각 별도의 창에서 실행되었습니다.
echo 각 창을 닫으면 해당 서비스가 종료됩니다.
pause
