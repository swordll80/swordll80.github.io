@echo off
setlocal

rem 切换到 bat 所在目录
cd /d "%~dp0"

rem 输出文件
set "OUT=list.txt"

rem 使用 PowerShell 生成 UTF-8 BOM 编码的 list.txt
rem 扫描当前目录及子目录下的 .kml 和 .yfxcache.zip 文件，输出相对路径，路径分隔符统一为 /
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$root = (Get-Location).Path; " ^
  "$files = Get-ChildItem -Path $root -Recurse -File | Where-Object { $_.Name -like '*.kml' -or $_.Name -like '*.yfxcache.zip' } | Sort-Object FullName | ForEach-Object { $_.FullName.Substring($root.Length).TrimStart('\\') -replace '\\','/' }; " ^
  "$utf8Bom = New-Object System.Text.UTF8Encoding($true); " ^
  "[System.IO.File]::WriteAllLines((Join-Path $root 'list.txt'), $files, $utf8Bom)"

echo Done: %OUT%
pause
