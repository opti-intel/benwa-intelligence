#!/bin/bash
# Opti Intel — dagelijkse PostgreSQL backup
# Sla dit script op in ~/benwa-intelligence/backup.sh
# Voeg toe aan cron: crontab -e  →  0 2 * * * /bin/bash ~/benwa-intelligence/backup.sh

set -euo pipefail

BACKUP_DIR="$HOME/opti-intel-backups"
DATUM=$(date +"%Y-%m-%d_%H-%M")
BESTAND="$BACKUP_DIR/opti_intel_$DATUM.sql.gz"
MAX_BACKUPS=30  # bewaar maximaal 30 dagelijkse backups

# Map aanmaken als die niet bestaat
mkdir -p "$BACKUP_DIR"

echo "🗄️  Backup starten: $BESTAND"

# Dump maken via de draaiende Docker container
docker exec benwa-intelligence-postgres-1 \
  pg_dump -U benwa benwa_intelligence \
  | gzip > "$BESTAND"

echo "✅ Backup klaar: $(du -sh "$BESTAND" | cut -f1)"

# Oude backups verwijderen (bewaar alleen de laatste MAX_BACKUPS)
AANTAL=$(ls -1 "$BACKUP_DIR"/*.sql.gz 2>/dev/null | wc -l)
if [ "$AANTAL" -gt "$MAX_BACKUPS" ]; then
  ls -1t "$BACKUP_DIR"/*.sql.gz | tail -n +$((MAX_BACKUPS + 1)) | xargs rm -f
  echo "🧹 Oude backups opgeruimd (bewaar laatste $MAX_BACKUPS)"
fi

echo "📁 Backup opgeslagen in: $BACKUP_DIR"
