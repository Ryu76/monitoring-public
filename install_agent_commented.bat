@echo off
chcp 65001 > nul

:: 에이전트 구동에 필요한 OS 모니터링 라이브러리(psutil) 및 HTTP 통신 라이브러리(requests)를 설치합니다.
:: (백엔드와 파이썬 가상환경을 공유하는 경우 이미 설치되어 있을 수 있습니다.)
pip install psutil requests

echo 에이전트 데몬 설치가 모두 완료되었습니다.
pause
