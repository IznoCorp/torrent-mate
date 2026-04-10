#!/usr/bin/env python
# -*- coding: utf-8 -*-
#

# Import moviepy editor : VideoFileClip
from moviepy.editor import VideoFileClip

###############################################################################

# Video infos.
video_name = "Strip-tease"
video_season = 3
video_episode_start = 1

# Original video file path.
original_video_filepath = "N:/a trier/007 EMISSIONS/Strip tease/S03E01 Strip-tease.Vol-03.avi"

# Episode timecode tuple. (élément à copier: ("00:00:00", "00:00:00"), )
episodes_timecodes = [
  ("00:13:50", "00:13:57"),
  ("00:14:03", "00:28:17"),
  ("00:28:24", "00:43:48"),
  ("00:43:55", "00:57:26"),
  ("00:57:34", "01:49:13"),
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
  
