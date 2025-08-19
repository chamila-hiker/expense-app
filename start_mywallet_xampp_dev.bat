@echo off
setlocal

REM ==== adjust these if your paths differ ====
set "PROJECT=D:\projects\expense-app"
set "VENV=%PROJECT%\.venv"
set "PY=%VENV%\Scripts\python.exe"
set "APPPORT=5000"
set "DBPORT=3306"

REM XAMPP MySQL options (service or direct EXE)
set "MYSQL_SERVICE=xamppmysql"   REM try xamppmysql; if you installed as "mysql", change it
set "XAMPP_MYSQL_EXE=C:\xampp\mysql\bin\mysqld.exe"
set "MYSQL_INI=C:\xampp\mysql\bin\my.ini"
REM ===========================================

cd /d "%PROJECT%"

REM --- free port 5000 (quietly) ---
powershell -NoProfile -Command ^
  "Get-NetTCPConnection -LocalPort %APPPORT% -State Listen | Select -Expand OwningProcess | ForEach-Object { try { Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue } catch {} }" >NUL 2>&1

REM --- start MySQL: service if present, else start mysqld.exe ---
sc.exe query "%MYSQL_SERVICE%" >NUL 2>&1
if %errorlevel%==0 (
  sc.exe start "%MYSQL_SERVICE%" >NUL 2>&1
) else (
  if exist "%XAMPP_MYSQL_EXE%" (
    echo Starting XAMPP MySQL directly...
    start "" /min "%XAMPP_MYSQL_EXE%" --defaults-file="%MYSQL_INI%" --standalone
  ) else (
    echo [WARN] Could not find a MySQL service or "%XAMPP_MYSQL_EXE%".
    echo        Start MySQL in XAMPP first, then press any key to continue.
    pause >NUL
  )
)

REM --- wait up to 20s for port 3306 to respond ---
for /l %%i in (1,1,20) do (
  powershell -NoProfile -Command ^
    "$c=New-Object Net.Sockets.TcpClient; $ok=$false; try{$c.Connect('127.0.0.1',%DBPORT%); $ok=$c.Connected}catch{}finally{$c.Close()}; if($ok){exit 0}else{exit 1}" >NUL 2>&1
  if not errorlevel 1 goto :db_ready
  timeout /t 1 >NUL
)
echo [ERROR] MySQL not listening on %DBPORT%. Start it in XAMPP and re-run.
pause
exit /b 1

:db_ready
REM --- background waiter to open browser AFTER 5000 is live ---
powershell -NoProfile -WindowStyle Hidden -Command ^
  "for($i=0;$i -lt 60;$i++){try{$c=New-Object Net.Sockets.TcpClient;$c.Connect('127.0.0.1',%APPPORT%);if($c.Connected){Start-Process 'http://127.0.0.1:%APPPORT%/';break}}catch{}finally{if($c){$c.Close()}};Start-Sleep -Milliseconds 500}"

REM --- run Flask with reloader (dev mode) ---
set "MYWALLET_DEBUG=1"
set "FLASK_APP=src.app"
set "FLASK_RUN_HOST=127.0.0.1"
set "FLASK_RUN_PORT=%APPPORT%"

"%PY%" -m flask run --debug

endlocal
