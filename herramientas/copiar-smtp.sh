#!/bin/sh
# Copia las credenciales SMTP de monitoring al .env de pajaritos.
# El valor nunca se imprime: pasa de un fichero a otro y solo se informa del largo.
set -e
ORIGEN=/volume1/docker/monitoring/.env
DESTINO=/volume1/docker/pajaritos/.env
[ -f "$ORIGEN" ] || { echo "no existe $ORIGEN"; exit 1; }
[ -f "$DESTINO" ] || { echo "no existe $DESTINO"; exit 1; }

cp -p "$DESTINO" "$DESTINO.bak-$(date +%Y%m%d%H%M%S)"

leer() { grep -m1 "^$1=" "$ORIGEN" | cut -d= -f2- | tr -d '"' | tr -d "'" | tr -d ' \r'; }
poner() {                       # poner CLAVE VALOR
  k="$1"; v="$2"
  tmp="$DESTINO.tmp.$$"
  grep -v "^$k=" "$DESTINO" > "$tmp" || true
  printf '%s=%s\n' "$k" "$v" >> "$tmp"
  mv "$tmp" "$DESTINO"
}

H=$(leer SMTP_HOST); P=$(leer SMTP_PORT); U=$(leer SMTP_USER); C=$(leer SMTP_PASS)
[ -n "$C" ] || { echo "monitoring/.env no tiene SMTP_PASS"; exit 2; }

poner SMTP_HOST "$H"
poner SMTP_PORT "${P:-587}"
poner SMTP_USER "$U"
poner SMTP_PASS "$C"

# Las de la API de Mailgun ya no las lee nadie: fuera, para no dejar
# variables muertas que confundan al siguiente que abra el fichero.
tmp="$DESTINO.tmp.$$"
grep -v "^MAILGUN_" "$DESTINO" > "$tmp" || true
mv "$tmp" "$DESTINO"

chmod 600 "$DESTINO"
echo "escrito $DESTINO"
echo "  SMTP_HOST=$H  SMTP_PORT=${P:-587}  SMTP_USER=$U  SMTP_PASS=<${#C} caracteres>"
echo "  ALERT_EMAIL=$(grep -m1 '^ALERT_EMAIL=' "$DESTINO" | cut -d= -f2-)"
echo "  lineas MAILGUN_ restantes: $(grep -c '^MAILGUN_' "$DESTINO" || true)"
