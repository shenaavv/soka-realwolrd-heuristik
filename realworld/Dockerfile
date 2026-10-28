FROM python:3.12-slim
COPY worker/worker.py /worker.py
ENV PYTHONUNBUFFERED=1
CMD ["python", "/worker.py"]
