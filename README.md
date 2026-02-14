# Email IQ

Email management and task automation tool.

## Getting started

1. Create a `.env` file (or rely on defaults) with:
   - `DEBUG=True`
   - `SECRET_KEY=...`
   - `DATABASE_URL=postgres://user:pass@localhost:5432/email_iq`
   - `CELERY_BROKER_URL` and `CELERY_RESULT_BACKEND` pointing to Redis.
2. Install dependencies in a virtualenv: `pip install -r requirements.txt`.
3. Run `make build` — it runs migrations and collects static files.
4. Start the development server with `make run` or use the Docker command below.

## Running the project

### Using Make (local development)
```bash
make run
```
This starts the Django development server on `http://0.0.0.0:8000`.

### Using Docker Compose
```bash
docker compose up
```
This starts all services (web server, Celery worker, Celery beat, and Redis) in containers.

## Structure

- `accounts`: account metadata for Gmail/Microsoft connectors.
- `mail`: cached threads/messages, drafts, attachments.
- `jobs`: Job and Task lifecycles.
- `automation`: Labels, Actions, and linking metadata.

## Next steps

- Flesh out DRF serializers/views/tests.
- Add Tailwind templates and base layout.
- Implement Celery tasks and OpenAI action runner.
- Dockerize for App Platform + add data fixtures.
