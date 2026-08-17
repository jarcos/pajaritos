#!/bin/sh
# Crea /volume1/docker/pajaritos/.env en el NAS si no existe. Idempotente.
# Los secretos se generan aquí, no se transportan.
set -e
cd /volume1/docker/pajaritos

if [ -f .env ]; then
  echo ".env ya existe: no se toca"
else
  TOKEN=$(openssl rand -base64 32)
  {
    echo "# Generado en el despliegue inicial. chmod 600. NUNCA commitear."
    echo ""
    echo "# -- Aviso de reportes nuevos (Mailgun EU) --"
    echo "# Vacio a proposito: sin clave la API omite el correo y el reporte SI"
    echo "# se guarda en SQLite. Rellenar cuando haya credenciales."
    echo "MAILGUN_API_KEY="
    echo "MAILGUN_DOMAIN="
    echo "MAILGUN_BASE_URL=https://api.eu.mailgun.net/v3"
    echo "ALERT_EMAIL=josearcoscampos@gmail.com"
    echo ""
    echo "# -- Antiabuso del endpoint de reportes --"
    echo "HONEYPOT_FIELD=telefono"
    echo "MIN_FILL_SECONDS=3"
    echo ""
    echo "# -- Token del healthcheck interno --"
    echo "INTERNAL_TOKEN=$TOKEN"
  } > .env
  chmod 600 .env
  echo ".env creado"
fi

ls -l .env
echo "--- claves definidas (sin mostrar valores) ---"
grep -E '^[A-Z_]+=' .env | while IFS='=' read -r k v; do
  if [ -n "$v" ]; then echo "  $k = (con valor)"; else echo "  $k = (vacio)"; fi
done
