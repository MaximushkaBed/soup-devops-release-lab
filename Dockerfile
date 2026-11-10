# Immutable Python base; update deliberately with the dependency locks.
FROM python:3.12-slim@sha256:5e2bdb1b0d542d5039cffb8181c65930093949194a65c365dfb1b0fe13a4fa5b
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /opt/soup
COPY bundle/dist/*.whl /tmp/wheels/
RUN python -m pip install --no-cache-dir --no-index --no-deps /tmp/wheels/*.whl
USER 65532:65532
# getpass needs a deterministic username even when the UID has no passwd entry.
ENV USER=soup
ENTRYPOINT ["soup-release"]
