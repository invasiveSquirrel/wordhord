#!/bin/bash
for i in {1..500}
do
  echo "Iteration $i"
  /home/chris/wordhord/backend/venv/bin/python3 /home/chris/wordhord/generate_once.py 20
  sleep 1
done
