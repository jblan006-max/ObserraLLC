FROM python:3.11-slim
WORKDIR /app
COPY agent.py /app/agent.py
RUN pip install --no-cache-dir fastapi uvicorn
EXPOSE 5000
CMD ["python", "agent.py"]
