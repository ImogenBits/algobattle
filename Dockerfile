FROM python:3.10

WORKDIR /usr/src/algobattle
COPY ../algobattle algobattle
COPY ../pyproject.toml .
COPY MANIFEST.in .
RUN pip install --no-cache-dir .

CMD ["--help"]
ENTRYPOINT ["algobattle"]