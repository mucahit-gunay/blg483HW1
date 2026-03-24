@echo off
echo === Web Crawler Kurulum ve Calistirma ===
echo.

REM Sanal ortam (venv) yoksa olustur
if not exist "venv\" (
    echo [1/3] Sanal ortam (venv) olusturuluyor...
    python -m venv venv
)

REM Sanal ortamı aktif et ve gereksinimleri kur
echo [2/3] Paketler yukleniyor...
call venv\Scripts\activate
pip install -r requirements.txt

REM Sunucuyu baslat
echo [3/3] Sunucu 3600 portunda baslatiliyor...
echo Tarayicidan su adrese gidebilirsiniz: http://localhost:3600
python server.py

pause
