#!/usr/bin/env python
# -*- coding: utf-8 -*-
#

# Import moviepy editor : VideoFileClip
from moviepy.editor import VideoFileClip

###############################################################################

# Video infos.
video_name = "Alf"
video_season = 1
video_episode_start = 2

# Original video file path.
original_video_filepath = "ALF Saison.1.1.avi"

# Episode timecode tuple.
episodes_timecodes = [
  ("00:24:15", "00:48:58"),
  ("00:48:58", "01:12:43"),
  ("01:12:43", "01:37:27"),
  ("01:37:27", "02:02:11"),
  ("02:02:11", "02:25:41"),
  ("02:25:41", "02:50:25"),  
]

###############################################################################
     
# Create video clip with original video file.
original_video = VideoFileClip(original_video_filepath) 

# Episodes counter.
episodes_count = 0

# For each episode timecode tuple.
for episode_timecodes in episodes_timecodes :
  # Get start and end timecode.
  start_timecode = episode_timecodes[0]
  end_timecode = episode_timecodes[1]
  # getting only first 15 seconds 
  sub_video = original_video.subclip(start_timecode, end_timecode)
  # saving the sub video clip.
  sub_video.write_videofile(f"{video_name} - S{video_season:02d}E{(video_episode_start + episodes_count):02d}.mp4")
  # Increase episode count.
  episodes_count += 1
  
