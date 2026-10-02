# Preserve the existing PostgreSQL major, Alpine distribution and volume path.
FROM postgres:17-alpine@sha256:b0f9560a2de083e2cc7382e75f808c7381a32852a7ec49117deedb300e552b24
ADD --checksum=sha256:cac0b10c360f05b2d521200105ba3697e773d4cd3731f5a915a7e37ebe0bea85 https://codeload.github.com/pgvector/pgvector/tar.gz/refs/tags/v0.8.7 /tmp/pgvector.tar.gz
RUN apk add --no-cache --virtual .vector-build build-base \
    && mkdir /tmp/pgvector \
    && tar -xzf /tmp/pgvector.tar.gz -C /tmp/pgvector --strip-components=1 \
    && make -C /tmp/pgvector -j2 with_llvm=no OPTFLAGS="" \
    && make -C /tmp/pgvector install with_llvm=no \
    && apk del .vector-build \
    && rm -rf /tmp/pgvector /tmp/pgvector.tar.gz
