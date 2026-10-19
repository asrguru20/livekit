# Interlan media reliability backports

This branch starts at the official **v1.13.10** release and carries the six
merged upstream changes recorded in `backports.json`. It does not track master
automatically. The custom artifact version is **1.13.10-interlan.2**; the
upstream protocol version string stays at 1.13.10. The binary's Go VCS metadata
and the build manifest identify the exact fork commit.

The fixes cover pause/probe recovery, source-switch timestamp wrap, timestamp
continuity after receiver restart, and the RTCP clock domain. v1.13.10 already
contains the RTX NACK and padding-payload fixes (#5000 and #4993).

The only cherry-pick conflict was the client-configuration test context in
#5019. The v1.13.10 Firefox/AV1 policy and its assertions are retained; the
Chrome assertion/comment remains. No codec policy, pacing algorithm, FEC,
dependency version, TURN setting or application role policy is changed.

## Verify on a separate Linux machine

Use **Go 1.27.1**, Python 3, Git, a C compiler for `-race`, and an authenticated
module proxy. A mirror can be selected through `GOPROXY`; keep `GOSUMDB` enabled.
The build helper refuses disabled checksum verification and modified sources.

```sh
git clone --branch codex/interlan-1.13.10-media-recovery https://github.com/asrguru20/livekit.git
cd livekit
export GOMAXPROCS=1 GOMEMLIMIT=1GiB GOTOOLCHAIN=local
# Optional network fallback; each source still uses checksum verification.
export GOPROXY='https://goproxy.cn|https://proxy.golang.org|direct'
export GOSUMDB=sum.golang.org

python3 deploy/interlan/test-backports.py --logs ../interlan-results
go test -p=1 -count=1 -timeout=15m ./pkg/sfu/... ./pkg/clientconfiguration
go test -p=1 -race -count=1 -timeout=10m \
  -run '^Test(ForwarderSwitchBackAfterReferenceTimestampWrap|ForwarderRestartKeepsTimestampContinuity|ForwarderSkipReferenceTSRestartNoOffset)$' ./pkg/sfu
```

For a shallow clone, fetch the immutable production-file control revisions:

```sh
git fetch --no-tags --depth=1 https://github.com/livekit/livekit.git \
  e5655ac20267fa5005dccaf3f0e3bfc3ea688c07 \
  e357fdffb77a084a308e0284c31004e531fa4046 \
  103d7bec847a21581e3d4d8ac5518330bf22196f
```

`test-backports.py` first requires all five named regressions to pass. In an
isolated source archive it then restores earlier production files while
retaining the fixed tests. Each control must fail in its named test and emit
the expected regression diagnostic. Download, compilation and general timeout
errors cannot count as a successful negative control. JSON logs and
`summary.json` are preserved outside the checkout.

The added sender-report test covers unknown arrival time being incorrectly
reported as the Unix epoch. It does not simulate a host NTP clock adjustment.

## Build artifacts without publishing

After verification, from a clean checkout:

```sh
bash deploy/interlan/build.sh ../interlan-artifacts
# Optional: package the same static binary over the pinned official runtime.
BUILD_IMAGE=1 bash deploy/interlan/build.sh ../interlan-artifacts
```

Set `GO=/absolute/path/to/go` if needed. The helper writes a Linux/amd64
binary, SHA256/source manifest and `go version -m` output. The optional image
is tagged `asrguru/livekit-server:v1.13.10-interlan.2` and records the fork
revision in OCI labels. It is built locally; neither command pushes an image
or changes a running service.

The helper checks source cleanliness and toolchain identity, and rejects
changes to `go.mod` or `go.sum` caused by the build. Preserve the test logs
with the resulting manifest. Build success is separate from test success.

## Application acceptance before any production rollout

Confirm the actual join policy is `SubscriberAllowPause=true` for both the
teacher and student in the test. Interlan Classroom 0.41.14 still explicitly
disables it for teachers. Compare the same network profile before and after
these patches, and require decoded and displayed frames, not just received
bytes. Subtract dropped frames and account for element/counter replacement.

Measure audio concealment, discarded/late packets and jitter-buffer delay in
the same windows. Exercise camera stop/start, simulcast layer changes,
screen-sharing, recording, and the transports/devices used by the class.
These source regressions do not establish performance on Iranian networks,
Safari or Android. Rollout and changing the classroom role policy are separate
operations from preparing this fork.
