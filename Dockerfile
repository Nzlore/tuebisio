FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

EXPOSE 8501

ENV OPENAI_API_KEY=""

CMD ["streamlit", "run", "simple_questions.py"] 