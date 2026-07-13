@echo off
chcp 65001 > nul

:: 백엔드(FastAPI) 프로젝트 폴더로 이동합니다.
cd backend

:: pip 패키지 매니저를 최신 버전으로 업데이트합니다.
python -m pip install --upgrade pip

:: requirements.txt에 명시된 파이썬 의존성 패키지들을 한 번에 설치합니다.
pip install -r requirements.txt

:: 최상위 폴더로 복귀합니다.
cd ..

echo 백엔드 환경 설치가 모두 완료되었습니다.
pause
