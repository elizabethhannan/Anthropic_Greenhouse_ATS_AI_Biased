#!/bin/zsh
# Watch the existing progress log; never starts or changes the scan.
cd /Users/elizabethhannan/Downloads/AnthropicBiasData || exit 1
mkdir .person_halfway_watch.lock 2>/dev/null || exit 0
trap 'rmdir .person_halfway_watch.lock' EXIT
while true; do
    completed=$(sed -n 's/.*"files_completed": \([0-9][0-9]*\).*/\1/p' person_scan_progress.log | tail -n 1)
    if [[ -n "$completed" && "$completed" -ge 195 ]]; then
        /usr/bin/osascript -e 'display notification "The Person scan has completed at least 195 of 389 files and is continuing. Check person_scan_progress.log for match counts." with title "Anthropic Person scan: halfway complete" sound name "Glass"'
        result=$?
        if [[ "$result" -eq 0 ]]; then
            date -u '+Halfway notification submitted at %Y-%m-%dT%H:%M:%SZ' > person_scan_halfway_notification.log
        fi
        exit "$result"
    fi
    if tail -n 1 person_scan_progress.log | /usr/bin/grep -q 'Scan stopped safely'; then
        /usr/bin/osascript -e 'display notification "The Person scan stopped before the halfway milestone. Its checkpoint is saved; check the scan log." with title "Anthropic Person scan needs attention"'
        exit 1
    fi
    sleep 15
done
