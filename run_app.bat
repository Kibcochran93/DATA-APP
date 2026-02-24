@echo off
echo ============================================
echo DATA-APP - Run Application
echo ============================================
echo.

REM Check if virtual environment exists
if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
    call venv\Scripts\activate.bat
    echo Installing dependencies...
    pip install -r requirements.txt
) else (
    call venv\Scripts\activate.bat
)

echo.
echo Starting application...
echo The app will open in your browser at http://localhost:8501
echo.
echo Press Ctrl+C to stop the server
echo.

streamlit run app.py

pause
