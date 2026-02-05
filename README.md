# LineMarking Email Ops

Minimal Django project scaffolding for the LineMarking email operations tool.

## Getting started

1. Create a `.env` file (or rely on defaults) with:
   - `DEBUG=True`
   - `SECRET_KEY=...`
   - `DATABASE_URL=postgres://user:pass@localhost:5432/line_marking`
   - `CELERY_BROKER_URL` and `CELERY_RESULT_BACKEND` pointing to Redis.
2. Install dependencies in a virtualenv: `pip install -r requirements.txt`.
3. Run `make build` — it runs migrations and collects static files.
4. Start the development server with `make run` or use the Docker command above.

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
