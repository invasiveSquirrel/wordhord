#!/bin/bash
# Start Phonethic IPA App
# Backend should already be running on 8001 (Wordhord Backend)

cd /home/chris/wordhord/frontend-ipa
npm run dev -- --port 5174
