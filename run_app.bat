@echo off
echo ============================================
echo DATA-APP - SEATS Data Validator
echo ============================================
echo.

REM Create/activate a local virtual environment on first run
if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
    call venv\Scripts\activate.bat
    echo Installing dependencies...
    pip install -r requirements.txt
) else (
    call venv\Scripts\activate.bat
)

REM Authentication is ON by default. For local development only you may bypass
REM it by setting TEST_MODE=true yourself before launching (never in production):
REM    set TEST_MODE=true

echo.
echo Starting SEATS Data Validator at http://localhost:8501
echo Press Ctrl+C to stop the server.
echo.

streamlit run app.py

pause
