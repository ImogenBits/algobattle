FROM python:3.10

WORKDIR /usr/src/algobattle
COPY ../algobattle algobattle
COPY ../pyproject.toml .
COPY ../setup.py .
COPY ../tests tests
RUN pip install --no-cache-dir .

ENTRYPOINT ["python", "-m", "unittest", "--failfast"]