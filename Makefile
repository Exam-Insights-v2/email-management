PYTHON=python3

.PHONY: build run test reset-db flush-db reset-postgres

build:
	$(PYTHON) manage.py migrate
	$(PYTHON) manage.py collectstatic --noinput

run:
	$(PYTHON) manage.py runserver 0.0.0.0:8000

test:
	$(PYTHON) manage.py test

# Flush database - clears all data but keeps schema
flush-db:
	$(PYTHON) manage.py flush --noinput

# Reset database completely - deletes database file (SQLite) or drops/recreates (PostgreSQL)
reset-db:
	@echo "Resetting database..."
	@if [ -f db.sqlite3 ]; then \
		rm db.sqlite3; \
		echo "Deleted SQLite database file"; \
	fi
	@echo "Running migrations to recreate database..."
	$(PYTHON) manage.py migrate
	@echo "Database reset complete!"

# Reset PostgreSQL database - unapplies all migrations (drops all tables) then reapplies them
reset-postgres:
	@echo "Resetting PostgreSQL database..."
	@echo "Unapplying all migrations (this will drop all tables)..."
	$(PYTHON) manage.py migrate accounts zero
	$(PYTHON) manage.py migrate mail zero
	$(PYTHON) manage.py migrate jobs zero
	$(PYTHON) manage.py migrate automation zero
	$(PYTHON) manage.py migrate contenttypes zero
	$(PYTHON) manage.py migrate auth zero
	$(PYTHON) manage.py migrate sessions zero
	$(PYTHON) manage.py migrate admin zero
	@echo "Reapplying all migrations..."
	$(PYTHON) manage.py migrate
	@echo "PostgreSQL database reset complete!"
