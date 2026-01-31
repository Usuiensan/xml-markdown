@echo off
setlocal

:: バッチファイルが存在するディレクトリに移動 (どこから実行してもこのフォルダを基準にする)
cd /d "%~dp0"

:: ==========================================================
:: 1. 環境設定 (相対パスへ変更)
:: ==========================================================

:: 仮想環境のPythonインタープリタの相対パス
:: (例: .venv/Scripts/python.exe)
set VENV_PYTHON=".\.venv\Scripts\python.exe"

:: 実行するPythonスクリプトの相対パス
set SCRIPT_PATH=".\xml-to-md.py"

:: ==========================================================
:: 2. 実行
:: ==========================================================

echo.
echo 仮想環境のPythonを実行します: %VENV_PYTHON%

:: Python実行前にファイルが存在するか確認 (エラーメッセージを明確にするため)
if not exist %VENV_PYTHON% (
    echo [エラー] 仮想環境のPythonが見つかりません。パスを確認してください。
    echo 期待されるパス: %VENV_PYTHON%
    pause
    goto :eof
)

if not exist %SCRIPT_PATH% (
    echo [エラー] Pythonスクリプトが見つかりません。
    echo 期待されるパス: %SCRIPT_PATH%
    pause
    goto :eof
)

:: startコマンドで新しいウィンドウを開いてPythonスクリプトを実行
start "XML to MD Converter" %VENV_PYTHON% %SCRIPT_PATH%

endlocal