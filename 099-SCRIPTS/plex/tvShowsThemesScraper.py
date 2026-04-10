#!/usr/bin/env python
# -*- coding: utf-8 -*-
#

""" Importing libraries """

from fileSystem import FileSystem
from youtubeScraper import YoutubeScraper
from decorators import timeit, cacheit
import os

""" Constants """

ROOT_PATH = os.path.dirname(os.path.abspath(__file__))
DRY_RUN = True

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

""" Class """

class tvShowsThemesScraper:

    """ TV shows themes scraper class """

    @staticmethod
    @timeit()
    @cacheit()
    def findTVShowsWithoutTheme(tvShowsPaths):

        """ 
            Find TV shows without theme
            ---
            Parameters:
                tvShowsPaths : List
                    List of TV shows paths
            ---
            Returns: List
                List of TV shows without theme
        """

        # TV shows without theme
        tvShowsWithoutTheme = []

        # Get TV shows folders
        tvShowsFolders = FileSystem.getSubFolders(tvShowsPaths)
        
        # Browse the TV shows folders
        for tvShowFolder in tvShowsFolders:
            
            # TV show dict info
            tvShow = {}

            # TV show folder path
            tvShow["folderPath"] = tvShowFolder

            # Get the TV show name
            tvShow["folderName"] = os.path.basename(tvShowFolder)

            # Remove the year from the TV show name
            tvShow["name"] = " (".join(tvShow["folderName"].split(" (")[:-1])

            # Create the theme file path.
            tvShow["themeFilePath"] = f"{tvShowFolder}/theme.mp3"

            # Check if the theme file exists
            if not os.path.exists(tvShow["themeFilePath"]):

                # Add the TV show to the list of TV shows without theme
                tvShowsWithoutTheme.append(tvShow)

        # Return the list of TV shows without theme
        return tvShowsWithoutTheme
    

    @staticmethod
    @timeit()
    #@cacheit()
    def getTvShowThemesMP3(tvShowName, path=f"{ROOT_PATH}/themes/"):

        """ 
            Get the TV show themes in mp3 format
            ---
            Parameters:
                tvShowName : String
                    TV show name
                path : String
                    Path to save the theme
            ---
            Returns: String
                Path to the theme.mp3 file
        """

        # YouTube API Search
        items = YoutubeScraper.search(f"{tvShowName} theme")

        # Get first item
        item = items[0]

        if DRY_RUN :
            print(f" - {item['title']}")
            print(f" - {item['url']}")
            return ""

        # Download the first items.
        downloadedFilePath = YoutubeScraper.download(item["url"], path)

        # Convert downloaded file to mp3
        mp3FilePath = YoutubeScraper.convert3gppToMP3(downloadedFilePath)

        # Rename the mp3 file
        os.rename(mp3FilePath, os.path.join(path, "theme.mp3"))

        # Delete the downloaded file
        os.remove(downloadedFilePath)

        # Return the mp3 file path
        return mp3FilePath



        

#####################################################################################################   
#                                            MAIN                                                   #
#####################################################################################################   

# Execute if run as script. 
if __name__ == "__main__":

    # Get TV shows without theme
    tvShowsWithoutTheme = tvShowsThemesScraper.findTVShowsWithoutTheme(TVSHOWS_PATHS)
    
    # Browse the TV shows without theme
    for tvShowWithoutTheme in tvShowsWithoutTheme:

        # Print the TV show name
        print(f"Downloading theme for \"{tvShowWithoutTheme['name']}\"...")

        # Execute the main function
        tvShowsThemesScraper.getTvShowThemesMP3(tvShowWithoutTheme["name"], tvShowWithoutTheme["folderPath"])

        # Print done
        print(" - Done.")

