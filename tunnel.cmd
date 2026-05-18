@echo off
chcp 65001 >nul
title Sapling + Cloudflare Tunnel

echo ========================================
echo   Sapling 教育 AI 助手 + Cloudflare Tunnel
echo ========================================
echo.

REM ---- 访问认证(修改为你自己的账号密码)----
set SAPLING_AUTH_USER=admin
set SAPLING_AUTH_PASS=sapling2026

echo [1/2] 启动 Gradio 应用...
start "Sapling-Gradio" python app.py
timeout /t 5 /nobreak >nul

echo [2/2] 启动 Cloudflare Tunnel...
echo.
echo 访问地址: https://你的域名
echo 账号: %SAPLING_AUTH_USER%
echo 密码: %SAPLING_AUTH_PASS%
echo.
echo 按 Ctrl+C 停止所有服务
echo ========================================

cloudflared tunnel run sapling
