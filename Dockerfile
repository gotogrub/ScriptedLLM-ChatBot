FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml README.md LICENSE ./
COPY src ./src
COPY data ./data
COPY static ./static

RUN pip install --no-cache-dir -e .

ENV CHATBOT_HOST=0.0.0.0
ENV CHATBOT_PORT=8080

EXPOSE 8080

CMD ["python", "-m", "chatbot"]
