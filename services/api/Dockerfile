FROM python:3.12-alpine3.20
# sqlite3 viene en la stdlib de Python: no hay que instalar nada para la base
# de datos. su-exec es para preparar el volumen como root y soltar privilegios.
RUN apk add --no-cache tzdata su-exec \
 && adduser -D -u 10001 pajaritos
WORKDIR /app
COPY app.py        /app/app.py
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh
ENV PYTHONUNBUFFERED=1 TZ=Europe/Madrid REPORTES_DB=/reportes/reportes.db
EXPOSE 8000
ENTRYPOINT ["/app/entrypoint.sh"]
