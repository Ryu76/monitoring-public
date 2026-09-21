@echo off
start "NexusMon Backend" cmd /c "cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000"
start "NexusMon Worker" cmd /c "cd backend && python -m app.worker_main"
start "NexusMon Frontend" cmd /c "cd frontend && npm run dev"
start "NexusMon Agent" cmd /c "timeout /t 5 /nobreak && python agent\agent.py"
echo Services are starting in separate windows...
pause
