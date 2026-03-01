# lightweight python container for the ESG intelligence app
FROM python:3.11-slim

# ensure dependencies are up-to-date
RUN apt-get update && \
    apt-get install -y --no-install-recommends build-essential && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# copy requirements and install before copying source (cache benefits)
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# copy the rest of the project
COPY . ./

# expose streamlit port
EXPOSE 8501

# default command
CMD ["streamlit", "run", "esg_app.py", "--server.port=8501", "--server.address=0.0.0.0"]
