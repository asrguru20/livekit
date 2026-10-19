#!/usr/bin/env python3
"""Run fixed regressions and reject invalid negative controls.

Controls replace production files in an isolated archive, retaining the fixed
tests. An expected failure needs a named test failure and its diagnostic, not
merely a non-zero process status. Logs remain available for independent review.
"""

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tarfile
import tempfile


ROOT = Path(__file__).resolve().parents[2]
BASE = "e5655ac20267fa5005dccaf3f0e3bfc3ea688c07"
REGRESSIONS = (
    "TestDownTrackResumesAfterBandwidthPause",
    "TestForwarderSwitchBackAfterReferenceTimestampWrap",
    "TestForwarderRestartKeepsTimestampContinuity",
    "TestForwarderSkipReferenceTSRestartNoOffset",
    "TestRTPStatsReceiverLastSenderReportTime",
)
CONTROLS = (
    ("pause", "pkg/sfu/downtrack.go", BASE,
     "TestDownTrackResumesAfterBandwidthPause", r"video did not resume within"),
    ("wrap", "pkg/sfu/forwarder.go", "e357fdffb77a084a308e0284c31004e531fa4046",
     "TestForwarderSwitchBackAfterReferenceTimestampWrap", r"switch point too far behind|switch point rejected"),
    ("restart", "pkg/sfu/forwarder.go", "103d7bec847a21581e3d4d8ac5518330bf22196f",
     "TestForwarderRestartKeepsTimestampContinuity", r"timestamp jumped"),
    ("skip-reference", "pkg/sfu/forwarder.go", "103d7bec847a21581e3d4d8ac5518330bf22196f",
     "TestForwarderSkipReferenceTSRestartNoOffset", r"Should be zero|timestamp jumped"),
    ("sender-report", "pkg/sfu/rtpstats/rtpstats_receiver.go", BASE,
     "TestRTPStatsReceiverLastSenderReportTime/zero_arrival_time",
     r"unknown sender report arrival must not look like"),
)


def git(*args):
    return subprocess.check_output(["git", "-C", str(ROOT), *args])


def execute(go, cwd, log, tests, packages):
    if len(tests) == 1:
        pattern = "/".join("^" + re.escape(part) + "$" for part in tests[0].split("/"))
    else:
        pattern = "^(" + "|".join(re.escape(test) for test in tests) + ")$"
    command = [go, "test", "-p=1", "-json", "-count=1", "-timeout=5m",
               "-run", pattern, *packages]
    print("Running " + log.stem, flush=True)
    # Write during execution as well, so a slow compile or download can be
    # diagnosed without waiting for the entire command or losing timeout logs.
    with log.open("w", encoding="utf-8") as stream:
        result = subprocess.run(command, cwd=cwd, text=True, stdout=stream,
                                stderr=subprocess.STDOUT, timeout=1800)
    output = log.read_text(encoding="utf-8")
    events = []
    for line in output.splitlines():
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            pass
    return result.returncode, events, output


def test_outcome(events, name, action):
    return any(e.get("Test") == name and e.get("Action") == action for e in events)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--go", default=os.environ.get("GO", "go"))
    parser.add_argument("--logs", type=Path, required=True)
    parser.add_argument("--positive-only", action="store_true")
    args = parser.parse_args()
    args.logs.mkdir(parents=True, exist_ok=True)
    summary = {"revision": git("rev-parse", "HEAD").decode().strip(), "checks": []}

    try:
        code, events, _ = execute(args.go, ROOT, args.logs / "fixed.jsonl",
                                  REGRESSIONS, ["./pkg/sfu", "./pkg/sfu/rtpstats"])
        if code or not all(test_outcome(events, t, "pass") for t in REGRESSIONS):
            raise RuntimeError("fixed tests did not all pass; see fixed.jsonl")
        summary["checks"].append({"name": "fixed", "result": "passed", "tests": list(REGRESSIONS)})
        print("Fixed regressions: PASS", flush=True)

        if not args.positive_only:
            with tempfile.TemporaryDirectory(prefix="interlan-livekit-controls-") as directory:
                scratch = Path(directory)
                archive = scratch / "source.tar"
                archive.write_bytes(git("archive", "HEAD"))
                control = scratch / "source"
                control.mkdir()
                # The archive is generated from this reviewed repository revision.
                with tarfile.open(archive) as source:
                    source.extractall(control)

                for label, filename, revision, test, diagnostic in CONTROLS:
                    destination = control / filename
                    fixed = destination.read_bytes()
                    destination.write_bytes(git("show", revision + ":" + filename))
                    package = "./pkg/sfu/rtpstats" if "/rtpstats/" in filename else "./pkg/sfu"
                    try:
                        code, events, output = execute(args.go, control,
                                                       args.logs / ("control-" + label + ".jsonl"),
                                                       [test], [package])
                    finally:
                        destination.write_bytes(fixed)
                    if not code or not test_outcome(events, test, "fail") or not re.search(diagnostic, output):
                        raise RuntimeError(label + ": expected named regression failure was not observed")
                    summary["checks"].append({"name": label, "result": "expected failure verified", "test": test})
                    print(label + ": expected regression failure VERIFIED", flush=True)

        summary["result"] = "passed"
    except Exception as error:
        summary["result"] = "failed"
        summary["error"] = str(error)
        raise
    finally:
        (args.logs / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
