@echo off
:: 폼폼 일일 자동 파이프라인 — Windows 작업 스케줄러로 등록
:: 매일 오전 8시 실행: python pompom/main.py auto

cd /d "C:\Users\cc009\Desktop\클로드 개발\숏폼 자동화 시스템"
call .venv\Scripts\activate.bat 2>nul || echo venv 없음, 시스템 Python 사용

python pompom\main.py auto >> pompom\output\daily_log.txt 2>&1
echo [%date% %time%] 실행 완료 >> pompom\output\daily_log.txt
