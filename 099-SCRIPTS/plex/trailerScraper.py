#!/usr/bin/env python
# -*- coding: utf-8 -*-
#

""" Importing libraries """

import shutil
import sys
from fileSystem import FileSystem
from youtubeScraper import YoutubeScraper
from decorators import timeit, cacheit
import os
import time
from colorama import Fore, Back, Style

""" Constants """

# Root path of the script
ROOT_PATH = os.path.dirname(os.path.abspath(__file__))
# Dry run mode
DRY_RUN = False
# Debug mode
DEBUG = False
# Download one trailer per season
ONE_TRAILER_PER_SEASON = False
# Force re-download of trailers, by deleting the existing ones
FORCE_REDOWNLOAD = False
# Clean trailers of the CLEAN_TRAILER_PATH
CLEAN_TRAILERS = False
# Trailer limit length (in seconds)
TRAILER_LIMIT_LENGTH = 600
# Trailer limit size (in MB)
TRAILER_LIMIT_SIZE = 70


# Medias paths
MEDIAS_PATHS = {
    "movies": [
        "/Volumes/DISK1/medias/films/",
        "/Volumes/DISK1/medias/films animations/",
        #"/Volumes/DISK1/medias/films documentaires/",
        "/Volumes/DISK1/medias/spectacles/",
        "/Volumes/DISK1/medias/theatres/",
        "/Volumes/DISK3/medias/films/",
        "/Volumes/DISK3/medias/films animations/",
        #"/Volumes/DISK3/medias/films documentaires/",
        "/Volumes/DISK3/medias/spectacles/",
    ],
    "tvshows": [
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
    ],
}

CLEAN_TRAILER_PATH = {
    "movies": [
        "/Volumes/DISK1/medias/films documentaires/",
        "/Volumes/DISK3/medias/films documentaires/",
    ]
}

""" Class """

class TrailerScraper:

    """ Download trailers from youtube class """

    @staticmethod
    #@timeit()
    @cacheit()
    def findMediasWithoutTrailer(mediasPaths, forceReDownload=False,  oneTrailerPerSeason=False, debug=False):
    
        """ 
            Browse the medias folders to find medias without trailer 
            ---
            Parameters:
                mediasPaths : Dict
                    Dict of medias type and list of media paths
                forceReDownload : Boolean
                    Force re-download of trailers, by deleting the existing ones
                oneTrailerPerSeason : Boolean
                    Download only one trailer per season
                debug : Boolean
                    Debug mode
            ---
            Returns: List
                List of medias without trailer
        """

        # Medias without trailer
        mediasWithoutTrailer = []
        
        # Browse the medias paths (movies and tvshows)
        for mediaType, mediaPaths in mediasPaths.items():

            # Get medias folders
            mediasFolders = FileSystem.getSubFolders(mediaPaths)

            # Check if mediaFolder is a subfolder of one of the MOVIES_PATHS entries
            isMovie = mediaType == "movies"

            # Check if mediaFolder is a subfolder of one of the TVSHOWS_PATHS entries
            isTVShow = mediaType == "tvshows"

            # Browse the medias folders
            for mediaFolder in mediasFolders:

                # Print the media folder name
                print(f"Media folder: {os.path.basename(mediaFolder)}")

                # Media without trailer object.
                mediaWithoutTrailer = {}

                # Get the media folder name
                mediaWithoutTrailer["folderName"] = os.path.basename(mediaFolder)

                # Get the media name from the folder name (remove the year) if it exists
                # Remove the last parenthesis and the content inside
                mediaWithoutTrailer["name"] = " (".join(mediaWithoutTrailer["folderName"].split(" (")[:-1])
                # if name is empty, set the name to the folder name
                if mediaWithoutTrailer["name"] == "":
                    mediaWithoutTrailer["name"] = mediaWithoutTrailer["folderName"]

                # Get the media folder path
                mediaWithoutTrailer["folderPath"] = mediaFolder

                # If it's a movie
                if isMovie:
                    # Search keywords
                    searchKeywords = "trailer bande annonce vf"
                    # Print the media is a movie
                    print(Fore.YELLOW + f"    - Media is a " + Fore.LIGHTCYAN_EX + "MOVIE" + Style.RESET_ALL)
                    # Set the media type
                    mediaWithoutTrailer["type"] = "movie"
                    # Get the year if it exists
                    mediaWithoutTrailer["year"] = mediaWithoutTrailer["folderName"].split(" (")[-1].split(")")[0]
                    # Get the media trailer name
                    mediaWithoutTrailer["trailerName"] = f"{mediaWithoutTrailer['name']}-trailer.mp4"
                    # Get the media trailer path
                    mediaWithoutTrailer["trailersToDowload"] = {
                        mediaWithoutTrailer["name"]+" "+mediaWithoutTrailer["year"]+" "+searchKeywords : 
                        os.path.join(mediaFolder, mediaWithoutTrailer["trailerName"])
                    }
                    # Check if the media trailer exists (mediaWithoutTrailer["trailerPath"] first value)
                    if not os.path.exists(list(mediaWithoutTrailer["trailersToDowload"].values())[0]):
                        # Add the media to the medias without trailer list
                        mediasWithoutTrailer.append(mediaWithoutTrailer)
                        # Print the media name
                        print(Fore.LIGHTMAGENTA_EX + f"    - Trailer not found" + Style.RESET_ALL)
                    else:
                        if forceReDownload :
                            # Delete the existing trailer
                            os.remove(list(mediaWithoutTrailer["trailersToDowload"].values())[0])
                            # Add the media to the medias without trailer list
                            mediasWithoutTrailer.append(mediaWithoutTrailer)
                            # Print force re-download message
                            print(Fore.LIGHTMAGENTA_EX + f"    - Force re-download" + Style.RESET_ALL)
                        else:
                            # Print the media name
                            print(Fore.GREEN + f"    - Trailer found" + Style.RESET_ALL)
                    
                # If it's a tv show
                if isTVShow:
                    # Search keywords
                    searchKeywords = "trailer bande annonce générique vf"
                    # Print the media is a tv show
                    print(Fore.YELLOW + f"    - Media is a " + Fore.LIGHTCYAN_EX + "TV SHOW" + Style.RESET_ALL)
                    # Set the media type
                    mediaWithoutTrailer["type"] = "tvshow"
                    # Get the year if it exists
                    mediaWithoutTrailer["year"] = mediaWithoutTrailer["folderName"].split(" (")[-1].split(")")[0]
                    # Get the season number by counting subfolders with name starting with "Saison"
                    mediaWithoutTrailer["season"] = len([name for name in os.listdir(mediaFolder) if os.path.isdir(os.path.join(mediaFolder, name)) and name.startswith("Saison")])
                    # Get the media trailer names for each season
                    mediaWithoutTrailer["trailerNames"] = [f"{mediaWithoutTrailer['name']} - Saison {season} - trailer.mp4" for season in range(1, mediaWithoutTrailer["season"] + 1)]
                    # Get the trailers folder path
                    mediaWithoutTrailer["trailersFolderPath"] = os.path.join(mediaFolder, "trailers")
                    # Check if we have to download the trailer for each season
                    if oneTrailerPerSeason : 
                        # Get the media trailers path mediaFolder + subfolder "trailers" + trailer name
                        mediaWithoutTrailer["trailersToDowload"] = {
                            mediaWithoutTrailer["name"]+" "+mediaWithoutTrailer["year"]+" Saison "+str(season)+" "+searchKeywords : 
                            os.path.join(mediaFolder, "trailers", mediaWithoutTrailer["trailerNames"][season - 1])
                            for season in range(1, mediaWithoutTrailer["season"] + 1)
                        }
                    else:
                        if len(mediaWithoutTrailer["trailerNames"]) > 1:
                            # Get the media trailers path mediaFolder + subfolder "trailers" + trailer name
                            mediaWithoutTrailer["trailersToDowload"] = {
                                mediaWithoutTrailer["name"]+" "+mediaWithoutTrailer["year"]+" "+searchKeywords : 
                                os.path.join(mediaFolder, "trailers", mediaWithoutTrailer["trailerNames"][0])
                            }
                        else:
                            # Get the media trailers path mediaFolder + trailer name
                            mediaWithoutTrailer["trailersToDowload"] = {
                                mediaWithoutTrailer["name"]+" "+mediaWithoutTrailer["year"]+" "+searchKeywords : 
                                os.path.join(mediaFolder, "trailers", f"{mediaWithoutTrailer['name']} - Saison 1 - trailer.mp4")
                            }
                    
                    # Check if the trailers folder not exists
                    if not os.path.exists(mediaWithoutTrailer["trailersFolderPath"]):
                        # Create the trailers folder
                        os.mkdir(mediaWithoutTrailer["trailersFolderPath"])
                        # Print the media name
                        print(Fore.YELLOW + f"    - Create trailers folder" + Style.RESET_ALL)

                    # Old naming convention trailer name
                    oldTrailerName = f"{mediaWithoutTrailer['name']}-trailer.mp4"
                    oldTrailerPath = os.path.join(mediaFolder, oldTrailerName)

                    # Print the old naming convention trailer name
                    #print(Fore.YELLOW + f"    - Old naming convention trailer name: " + f"{oldTrailerName}" + Style.RESET_ALL)

                    # Print parsing trailers message
                    if oneTrailerPerSeason:
                        print(Fore.YELLOW + f"    - Check for trailers :" + Style.RESET_ALL)
                    else:
                        print(Fore.YELLOW + f"    - Check for trailer :" + Style.RESET_ALL)

                    # Check if a trailer exists in the media folder matching the old naming convention
                    if os.path.exists(oldTrailerPath):
                        # Get the first trailer path
                        firstTrailerPath = list(mediaWithoutTrailer["trailersToDowload"].values())[0]
                        # Move the trailer as the first trailer
                        os.rename(oldTrailerPath, firstTrailerPath)
                        # Print 
                        print(Fore.YELLOW + f"    - One trailer found : moved to trailers folder" + Style.RESET_ALL)

                    # Check if seasons trailers exists (loop over a copy of the dict because we modify it in the loop)
                    for trailerPath in list(mediaWithoutTrailer["trailersToDowload"].values()):
                        # If the trailer exists
                        if os.path.exists(trailerPath):
                            # Print the trailer name
                            print(Fore.GREEN + f"        - {os.path.basename(trailerPath)}" + Style.RESET_ALL)
                            if forceReDownload :
                                # Delete the existing trailer
                                os.remove(trailerPath)
                                # Print force re-download message
                                print(Fore.YELLOW + f"        - Force re-download" + Style.RESET_ALL)
                            else:   
                                # Remove the trailer from the dict of trailers to download
                                mediaWithoutTrailer["trailersToDowload"].pop(list(mediaWithoutTrailer["trailersToDowload"].keys())[list(mediaWithoutTrailer["trailersToDowload"].values()).index(trailerPath)])
                        else:
                            # Print the trailer name
                            print(Fore.LIGHTMAGENTA_EX + f"        - {os.path.basename(trailerPath)}" + Style.RESET_ALL)
                    
                    # Check if there are trailers to download
                    if len(mediaWithoutTrailer["trailersToDowload"]) > 0:
                        # Add the media to the list of medias without trailer
                        mediasWithoutTrailer.append(mediaWithoutTrailer)
                        if not forceReDownload :
                            if not oneTrailerPerSeason :
                                # Print the media name
                                print(Fore.LIGHTMAGENTA_EX + f"    - Trailer not found" + Style.RESET_ALL)
                            else:
                                # Print the media name
                                print(Fore.LIGHTMAGENTA_EX + f"    - All trailers not found" + Style.RESET_ALL)
                    else:
                        if not oneTrailerPerSeason :
                            # Print the media name
                            print(Fore.GREEN + f"    - Trailer found" + Style.RESET_ALL)
                        else:
                            # Print the media name
                            print(Fore.GREEN + f"    - All trailer found" + Style.RESET_ALL)
                    

        # Return the list of medias without trailer
        return mediasWithoutTrailer

    @staticmethod
    def deleteTrailers(mediasPaths):

        """ 
            Delete the trailers of a media 
            ---
            Parameters:
                mediasPaths : List
                    List of medias paths
            ---
            Returns: None
        """
        
        # Browse the medias paths (movies and tvshows)
        for mediaType, mediaPaths in mediasPaths.items():

            # Get medias folders
            mediasFolders = FileSystem.getSubFolders(mediaPaths)

            # Check if mediaFolder is a subfolder of one of the MOVIES_PATHS entries
            isMovie = mediaType == "movies"

            # Check if mediaFolder is a subfolder of one of the TVSHOWS_PATHS entries
            isTVShow = mediaType == "tvshows"

            # Browse the medias folders
            for mediaFolder in mediasFolders:

                # Get folder name
                folderName = os.path.basename(mediaFolder)

                # Media name
                mediaName = " (".join(folderName.split(" (")[:-1])

                # Print the media name
                print(f"------------------------------------------------------------")
                print(f"Delete trailer(s) for {mediaName}")

                # if name is empty, set the name to the folder name
                if mediaName == "":
                    mediaName = folderName

                # If the media is a movie
                if isMovie:

                    # Get trailer name
                    trailerName = f"{mediaName}-trailer.mp4"

                    # Get trailer path
                    trailerPath = os.path.join(mediaFolder, trailerName)

                    # Check if the trailer exists
                    if os.path.exists(trailerPath):
                        # Delete the trailer
                        os.remove(trailerPath)
                        # Print the trailer name
                        print(Fore.LIGHTRED_EX + f"    - {trailerName} deleted" + Style.RESET_ALL)
                
                # If the media is a tvshow
                if isTVShow:

                    # Get trailers folder path
                    trailersFolderPath = os.path.join(mediaFolder, "trailers")

                    # Check if the trailers folder exists
                    if os.path.exists(trailersFolderPath):
                        # Delete the trailers folder and its content recursively
                        shutil.rmtree(trailersFolderPath)
                        # Print the trailers folder name
                        print(Fore.LIGHTRED_EX + f"    - trailers deleted" + Style.RESET_ALL)

        # End of the function
        return
    
    @staticmethod
    #@timeit()
    #@cacheit()
    def downloadTrailers(mediaInfos, limitLength=600, limitSize=50, debug=False):

        """ 
            Download the trailers of a media 
            ---
            Parameters:
                mediaInfos : Dict
                    Media infos dictionary
                limitLength : Integer
                    Limit length of the trailer in seconds
                limitSize : Integer
                    Limit size of the trailer in MB
                debug : Boolean
                    True if you want to print debug messages
            ---
            Returns: Boolean
                True if the trailers have been downloaded
        """

        # Browse the trailers to download
        for searchQuery, trailerPath in mediaInfos["trailersToDowload"].items():

            # Check if the trailer exists
            if not os.path.exists(trailerPath):
                # If DEBUG is True, print the search query
                if debug:
                    print(Fore.YELLOW + f"    - searchQuery : {searchQuery}" + Style.RESET_ALL)
                # Search the trailer on youtube
                searchItems = YoutubeScraper.search(searchQuery, 5)

                # Check if the trailer has been found
                if len(searchItems) > 0:
                    # Get the first item.
                    trailerInfos = searchItems[0]

                    # DEBUG 
                    if debug:
                        # Print infos in yellow
                        print(Fore.YELLOW + f"    - Media infos : {mediaInfos}" + Style.RESET_ALL)
                        print(Fore.YELLOW + f"    - Trailer infos : {trailerInfos}" + Style.RESET_ALL)
                    
                    # Download the trailer
                    downloadPath = YoutubeScraper.download(
                        trailerInfos['url'], 
                        trailerPath, 
                        lengthLimit=limitLength, 
                        sizeLimit=limitSize
                    )

                    # Check if the trailer has been downloaded
                    if not os.path.exists(downloadPath):
                        # Print error in red
                        print(Fore.RED + f"    - Error : Trailer not downloaded." + Style.RESET_ALL)
                        return False
                else:
                    # Print error in red
                    print(Fore.RED + f"    - Error : No trailer found." + Style.RESET_ALL)
                    return False
            else:
                # Print the trailer name
                print(Fore.GREEN + f"    - Trailer already exists" + Style.RESET_ALL)
                return False
            
        # Return True if the trailers have been downloaded
        return True
                    

#####################################################################################################   
#                                            MAIN                                                   #
#####################################################################################################   

# Execute if run as script. 
if __name__ == "__main__":

    # Clean the trailers if needed
    if CLEAN_TRAILERS:
        TrailerScraper.deleteTrailers(CLEAN_TRAILER_PATH)

    # Get medias without trailer
    mediasWithoutTrailer = TrailerScraper.findMediasWithoutTrailer(
        MEDIAS_PATHS, 
        forceReDownload=FORCE_REDOWNLOAD,
        oneTrailerPerSeason=ONE_TRAILER_PER_SEASON,
        debug=DEBUG
    )
    
    # Browse the medias without trailer
    for index, mediaWithoutTrailer in enumerate(mediasWithoutTrailer) :

        # If debug mode, print the media infos
        if DEBUG:
            print(Fore.YELLOW + f"    - Media folder : {mediaWithoutTrailer['folderPath']}" + Style.RESET_ALL)
            print(Fore.YELLOW + f"    - Media name : {mediaWithoutTrailer['name']}" + Style.RESET_ALL)
            print(Fore.YELLOW + f"    - Trailer path : {mediaWithoutTrailer['trailerPath']}" + Style.RESET_ALL)
        else:
            # Print the media name
            print(f"------------------------------------------------------------")
            print(f"Downloading trailer for \"{mediaWithoutTrailer['name']}\"...")

        # Download the trailer
        trailerDownloaded  = TrailerScraper.downloadTrailers(
            mediaWithoutTrailer, 
            limitLength=TRAILER_LIMIT_LENGTH,
            limitSize=TRAILER_LIMIT_SIZE,
            debug=DEBUG
        )
        # Check if the trailer has been downloaded
        if not DEBUG and not DRY_RUN and trailerDownloaded :
            # Print done in green
            print(Fore.GREEN + f"    - Done." + Style.RESET_ALL)
        elif trailerDownloaded :
            # Print one point every second during 3 seconds
            print(f"------------------------------------------------------------")
            print(Fore.LIGHTBLUE_EX + f"Waiting 3 seconds before next dowload", end="", flush=True)
            for i in range(3):
                print(".", end="", flush=True)
                time.sleep(1)
            print(Style.RESET_ALL)



        