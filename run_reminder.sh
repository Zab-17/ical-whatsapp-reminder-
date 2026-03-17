#!/bin/bash
# Canvas Reminder — runs the daily reminder
cd "/Users/zeyadkhaled/Desktop/claude skills/canvas-reminder"
/Library/Frameworks/Python.framework/Versions/3.12/bin/python3 -m src.reminder >> /tmp/canvas-reminder.log 2>&1
