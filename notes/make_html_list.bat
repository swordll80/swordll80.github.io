@echo off
setlocal

rem 切换到 bat 所在目录
cd /d "%~dp0"

rem 输出文件
set "OUT=list.txt"

rem 使用 PowerShell 生成 UTF-8 BOM 编码的 list.txt
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$root = (Get-Location).Path; " ^
  "$files = Get-ChildItem -Path $root -Recurse -File -Filter '*.html' | Sort-Object FullName | ForEach-Object { $_.FullName.Substring($root.Length).TrimStart('\') -replace '\\','/' }; " ^
  "$utf8Bom = New-Object System.Text.UTF8Encoding($true); " ^
  "[System.IO.File]::WriteAllLines((Join-Path $root 'list.txt'), $files, $utf8Bom)"

echo Done: %OUT%
pause