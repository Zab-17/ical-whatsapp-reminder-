#!/bin/bash
# Canvas Reminder — runs the change detector
cd "/Users/zeyadkhaled/Desktop/claude skills/canvas-reminder"
/Library/Frameworks/Python.framework/Versions/3.12/bin/python3 -m src.detector >> /tmp/canvas-detector.log 2>&1
