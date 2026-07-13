@echo off
chcp 65001 > nul

:: 프론트엔드(Vue 3) 프로젝트 폴더로 이동합니다.
cd frontend

:: package.json에 정의된 Node.js 기반 프론트엔드 패키지들을 설치합니다.
npm install

:: 최상위 폴더로 복귀합니다.
cd ..

echo 프론트엔드 환경 설치가 모두 완료되었습니다.
pause
