FROM python:3.12-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py .
COPY index.html privacy.html reset.html terms.html ./static/
COPY simple-flow-fix.js ./static/simple-flow-fix.js
RUN python -c "from pathlib import Path; p=Path('/app/static/index.html'); s=p.read_text(encoding='utf-8'); tag='<script src=\"/simple-flow-fix.js\"></script>'; s=s if tag in s else s.replace('</body>', tag+'\\n</body>', 1); p.write_text(s, encoding='utf-8')"
RUN mkdir -p /app/data && useradd -r -u 10001 appuser && chown -R appuser:appuser /app
USER appuser
EXPOSE 10000
CMD ["sh", "-c", "uvicorn app:app --host 0.0.0.0 --port ${PORT:-10000} --proxy-headers --forwarded-allow-ips='*'"]
