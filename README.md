# Altium Financiero V12

Dashboard financiero en Streamlit con la pestaña Felicidad reorganizada y la Brújula Altium.

## Estructura

```text
Altium_Financiero_V12/
├── app.py
├── modules/
│   ├── __init__.py
│   ├── core.py
│   └── report_pdf.py
├── .streamlit/
│   └── config.toml
├── data/
│   └── .gitkeep
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── .dockerignore
├── iniciar_altium.bat
├── detener_altium.bat
├── iniciar_altium.sh
└── detener_altium.sh
```

## Requisitos

- Docker Desktop instalado y activo.
- Puerto `8501` disponible.

## Inicio rápido en Windows

Ejecute:

```text
iniciar_altium.bat
```

Luego abra:

```text
http://localhost:8501
```

Para detenerlo:

```text
detener_altium.bat
```

## Inicio manual

```bash
docker compose up -d --build
```

Ver registros:

```bash
docker compose logs -f
```

Detener:

```bash
docker compose down
```

## Construcción sin Docker Compose

```bash
docker build -t altium-financiero:v12 .
docker run -d --name altium-financiero-v12 -p 8501:8501 altium-financiero:v12
```

## Publicar en Docker Hub

Reemplace `USUARIO_DOCKERHUB` por su usuario:

```bash
docker login
docker tag altium-financiero:v12 USUARIO_DOCKERHUB/altium-financiero:v12
docker push USUARIO_DOCKERHUB/altium-financiero:v12
```

Opcionalmente publique también `latest`:

```bash
docker tag altium-financiero:v12 USUARIO_DOCKERHUB/altium-financiero:latest
docker push USUARIO_DOCKERHUB/altium-financiero:latest
```

## Datos

La aplicación carga el Excel desde el navegador. El volumen `altium_data` queda preparado para persistencia futura en `/app/data`, aunque la versión actual no necesita almacenar permanentemente el archivo cargado.

## Seguridad

No incluya archivos Excel personales, contraseñas ni `.streamlit/secrets.toml` dentro de la imagen antes de publicarla.
