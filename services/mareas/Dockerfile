FROM python:3.12-alpine3.20
# Sin dependencias: solo biblioteca estándar. Menos superficie, menos
# mantenimiento y nada de cadena de suministro que auditar.
RUN apk add --no-cache tzdata
WORKDIR /app
COPY fetch_mareas.py /app/fetch_mareas.py
COPY entrypoint.sh   /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh /app/fetch_mareas.py
ENV PYTHONUNBUFFERED=1 TZ=Europe/Madrid MAREAS_PATH=/datos/mareas.json
ENTRYPOINT ["/app/entrypoint.sh"]
