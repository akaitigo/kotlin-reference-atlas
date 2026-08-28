# SPDX-License-Identifier: Apache-2.0
FROM gradle:9.5.0-jdk17@sha256:dfb52c9c5247cf6129770cd60597bbc1e67cdcfb7fd3691ed450d1c60737ea9e

WORKDIR /workspace
ENV GRADLE_USER_HOME=/opt/atlas-gradle-home

COPY . /workspace
RUN gradle \
    :labs:jvm:test \
    :labs:semantics:test \
    :labs:coroutines:test \
    :labs:flow:test \
    :labs:interop:test \
    :labs:compiler-runtime:test \
    :labs:engineering:test \
    --no-daemon

CMD ["gradle", ":labs:jvm:test", ":labs:semantics:test", ":labs:coroutines:test", ":labs:flow:test", ":labs:interop:test", ":labs:compiler-runtime:test", ":labs:engineering:test", "--offline", "--no-daemon"]
