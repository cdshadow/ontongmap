@echo off
chcp 65001 >nul
setlocal

REM ============================================================
REM  ontongmap 일일 갱신 + GitHub 푸시
REM  1) 지도 생성 스크립트 실행 -> index.html 갱신
REM  2) 변경사항 커밋 후 원격에 푸시
REM  실패 시 exit code 1 (루틴이 실패를 인지할 수 있게)
REM ============================================================

set "REPO=D:\d\01_code\py\ontongmap"
set "PY=python"
set "SCRIPT=place_map_api(perfect)_v6_cl.py"
set "TARGET=index.html"

for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd"') do set "YMD=%%i"
for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format \"yyyy-MM-dd HH:mm:ss\""') do set "NOW=%%i"

set "LOGDIR=%REPO%\_log"
if not exist "%LOGDIR%" mkdir "%LOGDIR%"
set "LOG=%LOGDIR%\push_%YMD:~0,6%.log"

call :say "============================================================"
call :say "시작 %NOW%"

cd /d "%REPO%" || (call :say "[실패] 저장소 폴더로 이동 불가: %REPO%" & exit /b 1)

REM ---- 1. 지도 생성 ----------------------------------------
call :say "[1/4] %SCRIPT% 실행"
%PY% "%SCRIPT%" >> "%LOG%" 2>&1
if errorlevel 1 (
    call :say "[실패] 스크립트가 오류로 종료됨 (errorlevel %errorlevel%)"
    call :say "       위 로그의 파이썬 트레이스백을 확인할 것"
    exit /b 1
)

if not exist "%TARGET%" (
    call :say "[실패] %TARGET% 이 생성되지 않음"
    exit /b 1
)
call :say "      %TARGET% 확인됨"

REM ---- 2. 변경사항 확인 (index.html 만) ----------------------
call :say "[2/4] %TARGET% 변경 여부 확인"
git status --porcelain -- "%TARGET%" > "%TEMP%\ontongmap_status.txt"
for %%A in ("%TEMP%\ontongmap_status.txt") do set "CHANGED=%%~zA"
if "%CHANGED%"=="0" (
    call :say "      %TARGET% 변경 없음. 커밋/푸시를 건너뜀."
    call :say "      주의: 매일 동일하다면 스크립트가 실제로 갱신하는지 확인 필요"
    exit /b 0
)
type "%TEMP%\ontongmap_status.txt" >> "%LOG%"

REM ---- 3. 커밋 (index.html 만 스테이징) ----------------------
call :say "[3/4] 커밋"
git add "%TARGET%" >> "%LOG%" 2>&1
git commit -m "update ontongmap_%YMD%" -- "%TARGET%" >> "%LOG%" 2>&1
if errorlevel 1 (
    call :say "[실패] 커밋 실패. git 사용자 설정(user.name/user.email)을 확인할 것"
    exit /b 1
)

REM ---- 4. 푸시 ----------------------------------------------
REM --force-with-lease: 내가 마지막으로 본 원격 상태와 다르면 거부한다.
REM 평소엔 --force와 동일하게 동작하고, 남의 커밋을 지울 상황에서만 멈춘다.
call :say "[4/4] 푸시"
git push -u origin main --force-with-lease >> "%LOG%" 2>&1
if errorlevel 1 (
    call :say "[실패] 푸시 실패."
    call :say "       'stale info' 오류면 원격에 내가 모르는 커밋이 있다는 뜻."
    call :say "       git fetch 후 내용을 확인하고 수동으로 처리할 것."
    call :say "       인증 오류면 git config --get credential.helper 확인."
    exit /b 1
)

call :say "[완료] %YMD% 푸시 성공"
exit /b 0

:say
echo %~1
echo %~1 >> "%LOG%"
exit /b 0
