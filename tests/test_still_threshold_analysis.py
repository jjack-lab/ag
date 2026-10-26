from health_monitor import DetectionObservation
from scripts.analyze_still_threshold import replay


def test_replay_changes_only_still_threshold():
    frames = {
        index: [DetectionObservation(1, 1, 0.9, (index * 0.1, 10.0, 20.0, 20.0))]
        for index in range(210)
    }

    lower = replay(frames, 210, 10, 0.5)
    higher = replay(frames, 210, 10, 1.5)

    assert lower["still_alerts"] == 0
    assert higher["still_alerts"] == 1
    assert higher["unique_tracks_alerted"] == 1
