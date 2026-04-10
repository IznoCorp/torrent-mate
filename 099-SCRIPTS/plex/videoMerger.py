#!/usr/bin/env python
# -*- coding: utf-8 -*-
#

# Import Path form pathlib.
from pathlib import Path

# Import moviepy editor : VideoFileClip and concatenate_videoclips
from moviepy.editor import VideoFileClip, concatenate_videoclips

###############################################################################

# Define video values.
season_number = 1
episode_number = 1
episode_parts = 2

# Cut all video on start and end timecode. (if start and end timecode are not null)
start_timecode = None
end_timecode = None

###############################################################################

# Define videos names patterns.
video_name_pattern = "Alf - S{season_number:02d}E{episode_number:02d}.mp4"
video_name_part_pattern = "Alf - S{season_number:02d}E{episode_number:02d} - part{part_number}.mp4"

# Videos clips list.
episode_parts_clips = []

# For each part, check if video exist.
for part_number in range(1, (episode_parts + 1)) :
  
  # Episode part file name.
  episode_part_file_name = video_name_part_pattern.format(season_number=season_number, episode_number=episode_number, part_number=part_number)

  # Check if episode file exist.
  if Path(episode_part_file_name).is_file() :
    
    # If subclip timecodes are defined.
    if start_timecode and end_timecode :
      # DEBUG
      print(f"Cutting video on timecode.")
      # Create video subclip on timecodes with video file.
      episode_parts_clips.append(VideoFileClip(episode_part_file_name).subclip(start_timecode, end_timecode))
    else:
      # Create video clip with video file.
      episode_parts_clips.append(VideoFileClip(episode_part_file_name))
    
  else :
    
    # DEBUG
    print(f"Episode part '{episode_part_file_name}' not found.")

# Episode file name.
episode_file_name = video_name_pattern.format(season_number=season_number, episode_number=episode_number)

# DEBUG
print(f"Concatenate : {episode_parts_clips}")

# Concatenate all videos_clips files.
episode_clip = concatenate_videoclips(episode_parts_clips)

# Write episode file.
episode_clip.write_videofile(episode_file_name)