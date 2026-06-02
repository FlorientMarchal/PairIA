@echo off
REM ── PairIA — Script de démarrage Windows ──────────────────────────────────
chcp 65001 > nul

echo [PairIA] Démarrage...

REM ── Chemins ───────────────────────────────────────────────────────────────
set SCRIPT_DIR=%~dp0
set OLLAMA_EXE=C:\Users\Dell\Desktop\ollama-windows-amd64\ollama.exe
set QDRANT_EXE=%SCRIPT_DIR%qdrant-server\qdrant.exe

REM ── Configuration Ollama ──────────────────────────────────────────────────
set OLLAMA_HOST=0.0.0.0
set OLLAMA_ORIGINS=*
set OLLAMA_NUM_PARALLEL=2
set OLLAMA_MAX_LOADED_MODELS=1

REM ── Vérifications ─────────────────────────────────────────────────────────
if not exist "%OLLAMA_EXE%" (
    echo [ERREUR] Ollama introuvable : %OLLAMA_EXE%
    echo Modifiez la variable OLLAMA_EXE dans ce fichier.
    pause & exit /b 1
)

if not exist "%QDRANT_EXE%" (
    echo [ERREUR] Qdrant server introuvable : %QDRANT_EXE%
    echo Téléchargez qdrant.exe depuis https://github.com/qdrant/qdrant/releases
    echo et placez-le dans : %SCRIPT_DIR%qdrant-server\
    pause & exit /b 1
)

REM ── Lancement Qdrant server ────────────────────────────────────────────────
echo [PairIA] Démarrage Qdrant server (port 6333)...
set QDRANT__STORAGE__STORAGE_PATH=%SCRIPT_DIR%qdrant_db
start "Qdrant" "%QDRANT_EXE%"
timeout /t 2 /nobreak > nul

REM ── Lancement Ollama ──────────────────────────────────────────────────────
echo [PairIA] Démarrage Ollama...
start "Ollama" "%OLLAMA_EXE%" serve
timeout /t 3 /nobreak > nul

REM ── Lancement FastAPI multi-workers ───────────────────────────────────────
echo [PairIA] Démarrage FastAPI (4 workers)...
cd /d "%SCRIPT_DIR%"
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4

pause