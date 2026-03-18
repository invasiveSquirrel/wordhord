#!/bin/bash
counter=1
while true; do
  timestamp=$(date +"%Y-%m-%d %H:%M:%S")
  echo "[$timestamp] Starting pass #$counter..."
  /home/chris/wordhord/backend/venv/bin/python3 /home/chris/wordhord/generate_all.py
  echo "[$timestamp] Pass #$counter finished. Sleeping 10s before restart."
  ((counter++))
  sleep 10
done
