FROM registry.access.redhat.com/hi/rust:latest-builder@sha256:ef54124d698b67c7fc6cde0e269378897156faab32071ea3761e6ca1e8925b26 AS builder

ENV RUSTUP_INIT_SKIP_PATH_CHECK=yes
ENV PATH="/usr/local/cargo/bin:${PATH}"

RUN /bin/bash -o pipefail -c \
        "curl --proto '=https' --tlsv1.2 --silent --show-error --fail https://sh.rustup.rs \
            | sh -s -- -y --profile minimal --default-toolchain 1.96.0" \
    && rustc --version \
    && cargo --version

WORKDIR /app

COPY Cargo.toml Cargo.lock rust-toolchain.toml ./
COPY src ./src

RUN cargo build --locked --release

FROM registry.access.redhat.com/hi/core-runtime:latest@sha256:9eee418dffb012493df240703a4532a35df36905083b1db0e787fdfd9b327f60

ARG GIT_COMMIT=unknown
ARG GIT_BRANCH=unknown
ENV GIT_COMMIT=${GIT_COMMIT}
ENV GIT_BRANCH=${GIT_BRANCH}

COPY --from=builder /usr/lib64/libcrypto.so.3* /usr/lib64/
COPY --from=builder /usr/lib64/libssl.so.3* /usr/lib64/
COPY --from=builder /app/target/release/stockchartsalerts /usr/local/bin/stockchartsalerts

ENTRYPOINT ["/usr/local/bin/stockchartsalerts"]
