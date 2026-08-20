# Altium Financiero V14

Dashboard financiero en Streamlit con la pestaña Felicidad reorganizada y la Brújula Altium.

## Estructura

```text
Altium_Financiero_V13/
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
docker build -t altium-financiero:v13 .
docker run -d --name altium-financiero-v13 -p 8501:8501 altium-financiero:v13
```

## Publicar en Docker Hub

Reemplace `USUARIO_DOCKERHUB` por su usuario:

```bash
docker login
docker tag altium-financiero:v13 USUARIO_DOCKERHUB/altium-financiero:v13
docker push USUARIO_DOCKERHUB/altium-financiero:v13
```

Opcionalmente publique también `latest`:

```bash
docker tag altium-financiero:v13 USUARIO_DOCKERHUB/altium-financiero:latest
docker push USUARIO_DOCKERHUB/altium-financiero:latest
```

## Datos

La aplicación carga el Excel desde el navegador. El volumen `altium_data` queda preparado para persistencia futura en `/app/data`, aunque la versión actual no necesita almacenar permanentemente el archivo cargado.

## Correcciones de consistencia

- Los flujos mensuales conservan año y mes, evitando mezclar periodos de años diferentes.
- El presupuesto usa todos los meses del rango seleccionado, incluso cuando un mes no tiene gastos.
- Los filtros de categoría y subcategoría se aplican también al presupuesto comparado.
- El PDF preparado se invalida automáticamente cuando cambia el archivo o cualquier filtro.
- La pestaña Score y el informe PDF comparten exactamente el mismo cálculo de seis componentes.

## Hoja Patrimonio

La aplicación acepta la estructura: `Fecha`, `Clasificación`, `Tipo de producto`,
`Disponibilidad de efectivo`, `Liquidez`, `Categoría`, `Subcategoría`, `Descripción`,
`Entidad`, `Porcentaje`, `Valor actual` y `Observaciones`.

El valor neto se calcula automáticamente aplicando el porcentaje de propiedad. Los activos
se registran en positivo y los pasivos en negativo, incluso cuando no existe una columna
separada de saldo pendiente.

Si el libro contiene una hoja `Pasivos` —o `Deudas` en versiones anteriores—, sus saldos
se incorporan automáticamente al patrimonio como valores negativos. En ese caso, la hoja
`Patrimonio` se usa exclusivamente como fuente de activos para evitar duplicaciones.

## Seguridad

No incluya archivos Excel personales, contraseñas ni `.streamlit/secrets.toml` dentro de la imagen antes de publicarla.
