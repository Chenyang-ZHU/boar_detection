@echo off
chcp 65001 >nul
title 野猪检测工具 - 安装到桌面
cd /d "%~dp0"

echo ============================================
echo   野猪检测工具 · 安装到桌面
echo   Boar Detector - Install to Desktop
echo ============================================

if not exist "BoarDetector.exe" (
    echo   ❌ 没找到 BoarDetector.exe
    echo      请先双击「一键打包.bat」生成程序，再运行本脚本
    pause & exit /b 1
)

set "DESKTOP=%USERPROFILE%\Desktop"
echo   [1/2] 复制程序到桌面 ...
copy /y "BoarDetector.exe" "%DESKTOP%\野猪检测工具.exe" >nul
echo   [2/2] 创建桌面快捷方式 ...
powershell -Command "$sh=New-Object -COM WScript.Shell; $lnk=$sh.CreateShortcut([Environment]::GetFolderPath('Desktop')+'\野猪检测工具.lnk'); $lnk.TargetPath=[Environment]::GetFolderPath('Desktop')+'\野猪检测工具.exe'; $lnk.WorkingDirectory=[Environment]::GetFolderPath('Desktop'); $lnk.IconLocation=[Environment]::GetFolderPath('Desktop')+'\野猪检测工具.exe,0'; $lnk.Save()"
echo.
echo ============================================
echo   ✅ 已安装到桌面！
echo   双击桌面上「野猪检测工具」图标即可使用
echo ============================================
pause
