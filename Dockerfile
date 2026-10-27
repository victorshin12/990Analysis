FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt gunicorn

# App code + only the CSVs/JSON the explorer needs
COPY paths.py .
COPY web/ web/
COPY data/extract/delegation_results.csv data/extract/delegation_results.csv
COPY data/extract/governance_management_measures.csv data/extract/governance_management_measures.csv
COPY data/classify/mso_classified.csv data/classify/mso_classified.csv
COPY data/classify/mso_text_distinct.csv data/classify/mso_text_distinct.csv
COPY data/input/cbi_hospitals.json data/input/cbi_hospitals.json

ENV HOST=0.0.0.0
ENV PORT=8080
EXPOSE 8080

# Shell form so $PORT works on hosts that inject it (Render, Fly, etc.)
CMD gunicorn -b 0.0.0.0:${PORT:-8080} -w 1 --timeout 120 web.app:app
