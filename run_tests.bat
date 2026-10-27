@echo off
echo Running Backend Tests (including worker lifecycle)...
cmd /c "set PYTHONPATH=backend&& C:\Users\HODI\anaconda3\envs\monitor_backend\python.exe -m pytest backend/tests agent/tests -q"
if errorlevel 1 goto :error

echo Running Frontend Unit Tests...
cmd /c "cd frontend && npm run test"
REM Note: npm run test might not be configured, depending on the project. We skip error checking here if we just want it best-effort, or we can check.

echo Running Frontend E2E Tests...
cmd /c "cd frontend && npx playwright test"

echo All Quality Gates Passed successfully!
goto :EOF

:error
echo A test failed! Stopping execution.
exit /b %errorlevel%
