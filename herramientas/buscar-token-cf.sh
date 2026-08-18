#!/bin/sh
# Busca credenciales de Cloudflare por el Mac. NO imprime valores, solo dónde
# están y de qué tipo son, para decidir si alguna sirve para tocar el tunnel.
echo "=== ficheros de cloudflared ==="
ls -la "$HOME/.cloudflared" 2>/dev/null || echo "  sin ~/.cloudflared"

echo "=== variables en el entorno del shell ==="
grep -rhoE '(CLOUDFLARE|CF)_[A-Z_]+' \
  "$HOME/.zshrc" "$HOME/.zshenv" "$HOME/.zprofile" "$HOME/.bashrc" 2>/dev/null \
  | sort -u | sed 's/^/  /' || true

echo "=== .env por ~/Sites (solo nombres de clave) ==="
for f in "$HOME"/Sites/*/.env "$HOME"/Sites/*/*/.env; do
  [ -f "$f" ] || continue
  K=$(grep -aoE '^(CLOUDFLARE|CF)_[A-Z_]+' "$f" 2>/dev/null | sort -u | tr '\n' ' ')
  [ -n "$K" ] && echo "  ${f#$HOME/}: $K"
done

echo "=== llavero (solo nombres de entrada) ==="
security dump-keychain 2>/dev/null | grep -aoE '"svce"<blob>="[^"]*[Cc]loudflare[^"]*"' \
  | sort -u | head -10 | sed 's/^/  /' || echo "  nada o sin permiso"

echo "=== wrangler / cli de cloudflare ==="
ls -la "$HOME/.wrangler/config" 2>/dev/null | head -5 || echo "  sin wrangler"
which cloudflared wrangler flarectl 2>/dev/null | sed 's/^/  /' || echo "  sin CLIs"
