# ESG Intelligence Streamlit App

Lightweight portfolio ESG tracker built with Streamlit, SQLite and a simple
scoring engine.

## Running Locally

1. Create & activate a virtual environment:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Start the app:
   ```bash
   streamlit run main_app.py
   ```
4. Point your browser to `http://localhost:8501`.

## Docker Deployment

Build the image and run a container:

```bash
# build
docker build -t esg_app:latest .

# run (mont a volume for persistence if desired)
mkdir -p ./data
docker run -it --rm -p 8501:8501 -v "$PWD/data":/app jpc_esg_intelligence.db esg_app:latest
```

The database file will live in `./data/jpc_esg_intelligence.db` and
reports/evidence directories will be created alongside.

## CI / Container Registry

A GitHub Actions workflow is provided (`.github/workflows/docker.yml`) that
will build and push the container to Docker Hub whenever `main` is updated. To
use it, set the following repository secrets:

- `DOCKERHUB_USERNAME` – your Docker Hub user name
- `DOCKERHUB_TOKEN` – a personal access token or password

Once pushed, you can deploy the image on any container platform (Heroku,
DigitalOcean App Platform, AWS ECS/Fargate, etc.) by pulling
`<username>/esg_app:latest`.

## Streamlit Cloud

You can also deploy directly on [Streamlit Community Cloud](https://streamlit.io)
by connecting the GitHub repo and specifying `main_app.py` as the entrypoint.

1. Log in to Streamlit Community Cloud and click **New app**.
2. Select this repository and choose the `main` branch and **specify `main_app.py`** as the entry point (not `esg_app.py`).
   *If you accidentally select `esg_app.py` you'll encounter an encoding error when
   generating reports; that file is an older prototype and is now deprecated.*
3. The service will automatically install `requirements.txt` and start the app.
4. **Optional configuration**:
   - Set an `ADMIN_PASSWORD` secret in the app settings if you want to override
     the default `admin123` used for enabling dummy data.
   - You can also define any other environment variables (e.g. database URLs)
     via the Secrets panel.
5. After deployment, the URL provided by Streamlit will host the dashboard,
   and updates pushed to `main` will trigger a rebuild.

(The repo already contains a `requirements.txt` and the `Dockerfile` is not
used by Streamlit Cloud.)

> **Cleanup note:** the original `esg_app.py` script is deprecated and has been
> removed. Only `main_app.py` should be referenced going forward.

## Notes

- The app persists data in an SQLite file located next to the script; make sure
your chosen host provides a writable volume.
- For production consider replacing SQLite with a managed database and storing
evidence files in object storage.

- **Dummy data toggle**: an administrator can enable a toggle in the Manage
  sidebar to load a set of sample ESG entries for a leading agent (default
  CBRE). Loading dummy data automatically turns the toggle off and the control
  becomes unavailable; re‑enabling the toggle later requires the admin
  password (`admin123` by default). You may change this constant in
  `main_app.py` or hook it up to a secure secret store.
