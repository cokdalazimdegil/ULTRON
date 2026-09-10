#!/bin/bash
# ULTRON — macOS Otomatik Başlatma KURULUM
# Kullanım: bash autostart_kur.sh
# Plist'i bu bilgisayara göre dinamik üretir — sabit kullanıcı yolu gömmez.

BASE_DIR="$(cd "$(dirname "$0")" && pwd)"
PLIST_DST="$HOME/Library/LaunchAgents/com.ultron.assistant.plist"
LEGACY_PLIST="$HOME/Library/LaunchAgents/com.alp.jarvis.plist"
PYTHON_BIN="$(command -v python3 || echo /usr/bin/python3)"
PYTHON_DIR="$(dirname "$PYTHON_BIN")"

echo ""
echo "╔══════════════════════════════════════╗"
echo "║   U.L.T.R.O.N  Otomatik Başlatma    ║"
echo "╚══════════════════════════════════════╝"
echo ""

# LaunchAgents dizinini oluştur (yoksa)
mkdir -p "$HOME/Library/LaunchAgents"

# Zaten yüklüyse veya eski servis varsa önce kaldır
for srv in "com.ultron.assistant" "com.alp.jarvis"; do
    if launchctl list "$srv" &>/dev/null; then
        echo "⚙️  Önceki servis ($srv) kaldırılıyor..."
        launchctl unload "$HOME/Library/LaunchAgents/${srv}.plist" 2>/dev/null
    fi
done

# Plist'i bu makineye göre üret
cat > "$PLIST_DST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.ultron.assistant</string>
    <key>ProgramArguments</key>
    <array>
        <string>${PYTHON_BIN}</string>
        <string>${BASE_DIR}/main.py</string>
    </array>
    <key>WorkingDirectory</key>
    <string>${BASE_DIR}</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <false/>
    <key>StandardOutPath</key>
    <string>${BASE_DIR}/ultron.log</string>
    <key>StandardErrorPath</key>
    <string>${BASE_DIR}/ultron_error.log</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>${PYTHON_DIR}:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
        <key>HOME</key>
        <string>${HOME}</string>
    </dict>
</dict>
</plist>
EOF
echo "✅ Plist üretildi → $PLIST_DST"

# Yükle
launchctl load "$PLIST_DST"
echo "✅ LaunchAgent yüklendi"

echo ""
echo "╔══════════════════════════════════════╗"
echo "║           Kurulum Tamam!             ║"
echo "╚══════════════════════════════════════╝"
echo ""
echo "📌 ULTRON artık Mac'e her girişte otomatik açılır."
echo "   Loglar: $BASE_DIR/ultron.log"
echo ""
echo "⚠️  macOS Sonoma/Ventura'da ilk seferde:"
echo "   Sistem Ayarları → Genel → Oturum Açma Öğeleri"
echo "   → 'ULTRON' öğesine izin ver"
echo ""
echo "🛑 Kaldırmak için: bash autostart_kaldir.sh"
echo ""
