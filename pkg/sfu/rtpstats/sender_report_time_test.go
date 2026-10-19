// Copyright 2026 Interlan contributors.
// Licensed under the Apache License, Version 2.0.

package rtpstats

import (
	"testing"
	"time"

	"github.com/stretchr/testify/require"

	"github.com/livekit/protocol/livekit"
	"github.com/livekit/protocol/utils/mono"
)

func TestRTPStatsReceiverLastSenderReportTime(t *testing.T) {
	t.Run("no report", func(t *testing.T) {
		r := NewRTPStatsReceiver(RTPStatsParams{})
		require.True(t, r.LastSenderReportTime().IsZero())
	})

	t.Run("zero arrival time", func(t *testing.T) {
		r := NewRTPStatsReceiver(RTPStatsParams{})
		r.srNewest = &livekit.RTCPSenderReportState{}
		require.True(t, r.LastSenderReportTime().IsZero(),
			"unknown sender report arrival must not look like a stale report from the Unix epoch")
	})

	t.Run("recent report", func(t *testing.T) {
		r := NewRTPStatsReceiver(RTPStatsParams{})
		r.srNewest = &livekit.RTCPSenderReportState{At: mono.UnixNano() - (3 * time.Second).Nanoseconds()}
		age := time.Since(r.LastSenderReportTime())
		require.InDelta(t, 3.0, age.Seconds(), 0.25,
			"sender report arrival must be comparable with wall-clock time")
	})
}
