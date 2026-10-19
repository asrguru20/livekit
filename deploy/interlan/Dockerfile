# The upstream runtime supplies the original certificates, packages and entrypoint.
# The replacement binary and manifest are built from the reviewed fork revision.
ARG UPSTREAM_RUNTIME
FROM ${UPSTREAM_RUNTIME}
ARG REVISION
ARG RELEASE
LABEL org.opencontainers.image.source="https://github.com/asrguru20/livekit" \
      org.opencontainers.image.revision="${REVISION}" \
      org.opencontainers.image.version="${RELEASE}"
COPY --chmod=755 livekit-server /livekit-server
COPY build-manifest.json /usr/share/interlan-livekit/build-manifest.json
