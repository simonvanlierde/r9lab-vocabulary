# `just review-stack` builds this on every start; the dependency layer stays cached until uv.lock
# changes. The log and vocabulary come from the repository mounted at /repo.
FROM ghcr.io/astral-sh/uv:0.13.9-python3.14-trixie-slim
ENV UV_PROJECT_ENVIRONMENT=/venv UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
WORKDIR /build
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project --extra review
COPY README.md LICENSE ./
COPY src src
RUN uv sync --frozen --no-dev --no-editable --extra review
ENV PATH=/venv/bin:$PATH
WORKDIR /repo
EXPOSE 8740
CMD ["python", "-m", "r9lab_vocabulary.review", "--host", "0.0.0.0"]
