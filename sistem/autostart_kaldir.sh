#!/bin/bash
# ULTRON — macOS Otomatik Başlatma KALDIR
# Kullanım: bash autostart_kaldir.sh

echo ""
echo "╔══════════════════════════════════════╗"
echo "║  U.L.T.R.O.N  Otomatik Başlatma     ║"
echo "║         Kaldırılıyor...              ║"
echo "╚══════════════════════════════════════╝"
echo ""

for srv in "com.ultron.assistant" "com.alp.jarvis"; do
    plist="$HOME/Library/LaunchAgents/${srv}.plist"
    if [ -f "$plist" ]; then
        launchctl unload "$plist" 2>/dev/null && echo "✅ $srv servisi durduruldu"
        rm -f "$plist" && echo "✅ $plist silindi"
    fi
done

echo ""
echo "✔️  ULTRON artık otomatik açılmayacak."
echo ""
