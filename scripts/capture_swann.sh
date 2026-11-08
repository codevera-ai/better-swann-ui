#!/bin/sh
# Capture the Swann Mac app's loopback traffic for 60 seconds.
#
# The app always talks to 127.0.0.1 with a tunnel underneath, so the plain
# HTTP call to the recorder, and its Authorization header, only exists on
# loopback. That is what this reads.
#
# Run it with:  sudo sh scripts/capture_swann.sh
# Then, while it counts down, play a clip in the Swann app.

OUT=/tmp/swann-capture.pcap
SECONDS_TO_RUN=60

if [ "$(id -u)" -ne 0 ]; then
  echo "Run this with sudo:  sudo sh scripts/capture_swann.sh"
  exit 1
fi

rm -f "$OUT"
echo "Recording loopback for ${SECONDS_TO_RUN} seconds."
echo "Now go to the Swann app and play a clip."
echo

# Everything on loopback except the Swann tool's own web server.
tcpdump -i lo0 -s0 -w "$OUT" 'tcp and not port 8750' 2>/dev/null &
PID=$!

i=0
while [ "$i" -lt "$SECONDS_TO_RUN" ]; do
  sleep 1
  i=$((i + 1))
  printf "\r  %s seconds left   " "$((SECONDS_TO_RUN - i))"
done
printf "\r                          \r"

kill "$PID" 2>/dev/null
wait "$PID" 2>/dev/null

[ -n "$SUDO_USER" ] && chown "$SUDO_USER" "$OUT"
echo "Done. Saved to $OUT"
echo "Size: $(du -h "$OUT" | cut -f1)"
