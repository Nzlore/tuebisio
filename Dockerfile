FROM python:3.9-slim

WORKDIR /app

# Install poppler-utils before pip requirements
RUN apt-get update && apt-get install -y \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

EXPOSE 8501

ENV OPENAI_API_KEY=""

CMD ["streamlit", "run", "simple_questions.py"] 