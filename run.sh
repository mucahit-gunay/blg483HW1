#!/bin/bash
echo "=== Web Crawler Kurulum ve Calistirma ==="
echo ""

# Sanal ortam (venv) yoksa olustur
if [ ! -d "venv" ]; then
    echo "[1/3] Sanal ortam (venv) olusturuluyor..."
    python3 -m venv venv
fi

# Sanal ortamı aktif et ve gereksinimleri kur
echo "[2/3] Paketler yukleniyor..."
source venv/bin/activate
pip install -r requirements.txt

# Sunucuyu baslat
echo "[3/3] Sunucu 3600 portunda baslatiliyor..."
echo "Tarayicidan su adrese gidebilirsiniz: http://localhost:3600"
python3 server.py
