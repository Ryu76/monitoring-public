@echo off
start "NexusMon Backend" cmd /c "call conda activate monitor_backend && cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000"
start "NexusMon Worker" cmd /c "call conda activate monitor_backend && cd backend && python -m app.worker_main"
start "NexusMon Frontend" cmd /c "call conda activate monitor_frontend && cd frontend && npm run dev"
start "NexusMon Agent" cmd /c "timeout /t 5 /nobreak && call conda activate monitor_backend && cd agent && python agent.py"
echo Services are starting in separate windows...
pause
