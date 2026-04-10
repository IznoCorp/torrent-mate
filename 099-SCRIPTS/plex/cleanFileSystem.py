#!/usr/bin/env python
# -*- coding: utf-8 -*-
#

""" Importing libraries """

import sys
from fileSystem import FileSystem


""" Constants """

# Debug mode
DEBUG = False
# Dry run mode
DRY_RUN = False

# Video extensions
VIDEOS_EXTENSIONS = [".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".mpg", ".mpeg", ".m4v", ".webm", ".ts",  ".flv", ".f4v"]

# Define the path to the movies folders
MOVIES_PATHS = [
    "/Volumes/DISK1/medias/films/",
    "/Volumes/DISK1/medias/films animations/",
    "/Volumes/DISK1/medias/films documentaires/",
    "/Volumes/DISK1/medias/spectacles/",
    "/Volumes/DISK1/medias/theatres/",
    "/Volumes/DISK3/medias/films/",
    "/Volumes/DISK3/medias/films animations/",
    "/Volumes/DISK3/medias/films documentaires/",
    "/Volumes/DISK3/medias/spectacles/",        
]

# Define the path to the TV shows folders
TVSHOWS_PATHS = [
    "/Volumes/DISK1/medias/series/",
    "/Volumes/DISK1/medias/series animations/",
    "/Volumes/DISK1/medias/series documentaires/",
    "/Volumes/DISK1/medias/emissions/",
    "/Volumes/DISK2/medias/series/",
    "/Volumes/DISK2/medias/series animes/",
    "/Volumes/DISK3/medias/series/",
    "/Volumes/DISK3/medias/series animations/",
    "/Volumes/DISK3/medias/series documentaires/",
    "/Volumes/DISK3/medias/emissions/",
    "/Volumes/DISK4/medias/series/",
]

""" Decorators """

class CleanFileSystem:

    @staticmethod
    def run_cleaning_process(medias_paths, extensions, dry_run=False, debug=False):

        """ 
            Run cleaning process on specified path.
            ---
            Parameters:
                medias_paths: List
                    List of medias paths to clean
                extensions: List
                    List of file extensions
                dry_run: Boolean
                    If True, the script will not delete anything
                debug: Boolean
                    If True, the script will print debug messages
        """

        # Check if not a dry run.
        if not dry_run :
            # Print the start message
            print("BE CAREFUL, THIS SCRIPT WILL DELETE FOLDERS AND FILES FROM YOUR FILESYSTEM")
            # Ask for confirmation
            confirmation = input("Are you sure you want to continue ? (y/n) : ")
            # If confirmation is not 'y'
            if confirmation != 'y' :
                # Exit the script
                exit()
            else :
                # Print the start message
                print("Starting the cleaning process...")
        else :
            # Print the start message
            print("Starting the dry run...")

        # Get medias folders
        mediasFolders = FileSystem.getSubFolders(medias_paths)

        # Get empty folders from movies and TV shows folders
        emptyFolders = FileSystem.getEmptyFolders(mediasFolders, extensions)

        # Check if there is empty folders
        if len(emptyFolders) > 0 :
            # Clean empty folders from the filesystem
            FileSystem.removeFolders(emptyFolders, dry_run)
        else :
            # Print the no empty folders message
            print("No empty folders detected.")

        # Print the end message
        print("Cleaning process finished.")

        

#####################################################################################################   
#                                            MAIN                                                   #
#####################################################################################################   

# Execute if run as script. 
if __name__ == "__main__":

    # Check for parameters --debug and --dry-run
    if "--debug" in sys.argv :
        DEBUG = True
    if "--dry-run" in sys.argv :
        DRY_RUN = True
    
    # Execute the main function
    CleanFileSystem.run_cleaning_process(MOVIES_PATHS + TVSHOWS_PATHS, VIDEOS_EXTENSIONS, DRY_RUN, DEBUG)

