PYTHON=python3

.PHONY: build run test

build:
\t$(PYTHON) manage.py migrate
\t$(PYTHON) manage.py collectstatic --noinput

run:
\t$(PYTHON) manage.py runserver 0.0.0.0:8000

test:
\t$(PYTHON) manage.py test
