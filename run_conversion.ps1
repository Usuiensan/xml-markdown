# ==========================================================
# 1. 設定項目
# (変更なし)
# ==========================================================
$LawListFile = ".\law_list.txt"
$PythonExe = "D:/新しいフォルダー/xml-markdown/.venv/Scripts/python.exe"
$PythonScript = "d:/新しいフォルダー/xml-markdown/xml-to-md.py"

$TempInputFile = Join-Path $env:TEMP "law_input.txt"

# ==========================================================
# 2. 実行環境の確認 (変更なし)
# ==========================================================
# (中略)

# ==========================================================
# 3. 法令リストの読み込みとPythonの実行
# ==========================================================

Write-Host "--- 法令リストから自動処理を開始します ---" -ForegroundColor Yellow

Get-Content $LawListFile | ForEach-Object {
    $LawName = $_.Trim()

    # 空行またはコメント行をスキップ (変更なし)
    if ([string]::IsNullOrEmpty($LawName) -or $LawName.StartsWith(";")) {
        return
    }

    # (中略：処理開始メッセージ)
    Write-Host ""
    Write-Host "=================================================="
    Write-Host "[処理開始] 法令名: ""$LawName""" -ForegroundColor Cyan
    Write-Host "=================================================="

    # 1. Pythonの標準入力に渡す内容 (モード '1'、法令名、終了 '9') を一時ファイルに書き出す (変更なし)
    $InputLines = @(
        "1"
        $LawName
        "9"  # EOFError回避のため
    )
    $InputLines | Out-File -FilePath $TempInputFile -Encoding UTF8BOM -Force

    # 2. **エラー回避のため、cmd.exeの力を借りてリダイレクトを実行**
    #    'cmd /c' は、指定されたコマンドを実行して終了します。
    #    $PythonExe と $PythonScript のパスが空白を含む可能性があるため、すべてダブルクォートで囲みます。

    $Command = "`"$PythonExe`" `"$PythonScript`" < `"$TempInputFile`""
    cmd /c $Command
    
    # 3. 一時ファイルを削除 (変更なし)
    Remove-Item $TempInputFile -Force

    # (中略：処理完了メッセージ)
    Write-Host ""
    Write-Host "=================================================="
    Write-Host "[処理完了] 法令名: ""$LawName""" -ForegroundColor Green
    Write-Host "=================================================="
}

Write-Host ""
Write-Host "--- すべての法令の処理が完了しました ---" -ForegroundColor Yellow