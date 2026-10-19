#!/usr/bin/env bash
set -euo pipefail

root=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
cd "$root"
go_bin=${GO:-go}
output=${1:-"$root/../interlan-livekit-artifacts"}
mkdir -p "$output"
output=$(CDPATH= cd -- "$output" && pwd)

if [[ -n $(git status --porcelain --untracked-files=normal) ]]; then
  echo 'Build requires a clean, committed checkout. Put outputs outside it.' >&2
  exit 1
fi
expected=$(python3 -c 'import json; print(json.load(open("deploy/interlan/backports.json"))["go_version"])')
actual=$("$go_bin" version | awk '{print $3}')
if [[ "$actual" != "$expected" ]]; then
  echo "Expected $expected, got $actual; use the toolchain pinned by Dockerfile." >&2
  exit 1
fi
if [[ $("$go_bin" env GOSUMDB) == off ]]; then
  echo 'Checksum database is disabled; use an authenticated proxy or a verified offline dependency set.' >&2
  exit 1
fi

revision=$(git rev-parse HEAD)
parallelism=${GO_BUILD_PARALLELISM:-1}
CGO_ENABLED=0 GOOS=linux GOARCH=amd64 "$go_bin" build -p "$parallelism" \
  -trimpath -buildvcs=true -o "$output/livekit-server" ./cmd/server
git diff --exit-code HEAD -- go.mod go.sum
"$go_bin" version -m "$output/livekit-server" > "$output/go-build-info.txt"

python3 - "$output" "$revision" "$actual" <<'PY'
import datetime, hashlib, json, pathlib, subprocess, sys
out = pathlib.Path(sys.argv[1])
manifest = json.loads(pathlib.Path('deploy/interlan/backports.json').read_text())
manifest.update(source_revision=sys.argv[2], toolchain=sys.argv[3], platform='linux/amd64',
                built_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                binary_sha256=hashlib.sha256((out / 'livekit-server').read_bytes()).hexdigest())
manifest['source_objects'] = {
    path: subprocess.check_output(['git', 'rev-parse', 'HEAD:' + path], text=True).strip()
    for path in ('cmd', 'pkg', 'version', 'go.mod', 'go.sum')
}
(out / 'build-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
print('Built', manifest['release'], 'revision', manifest['source_revision'])
print('Binary SHA256:', manifest['binary_sha256'])
PY

if [[ ${BUILD_IMAGE:-0} == 1 ]]; then
  runtime=$(python3 -c 'import json; print(json.load(open("deploy/interlan/backports.json"))["upstream_runtime"])')
  release=$(python3 -c 'import json; print(json.load(open("deploy/interlan/backports.json"))["release"])')
  image=${IMAGE_TAG:-"asrguru/livekit-server:v$release"}
  docker build --platform linux/amd64 --network none \
    --build-arg "UPSTREAM_RUNTIME=$runtime" --build-arg "REVISION=$revision" \
    --build-arg "RELEASE=$release" -f deploy/interlan/Dockerfile -t "$image" "$output"
  docker image inspect --format '{{.Id}}' "$image" > "$output/docker-image-id.txt"
  echo "Built local image: $image"
fi

echo "Artifacts: $output"
