FROM mcr.microsoft.com/playwright/python:v1.55.0-jammy


WORKDIR /app

# Install Python deps
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copy your app
COPY . .

# Railway provides PORT
ENV PORT=8080
EXPOSE 8080

CMD ["python", "run.py"]
