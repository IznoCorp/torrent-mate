#!/usr/bin/env python
# -*- coding: utf-8 -*-
#

""" Importing libraries """

import json
import re
import time
from pyyoutube import Api
from pytube import YouTube
import requests
from bs4 import BeautifulSoup
import os
from decorators import timeit, cacheit
import subprocess
import sys
from colorama import Fore, Back, Style


""" Constants """

# YouTube API key
YOUTUBE_API_KEY = "AIzaSyAEpj2d8w8ofneUNFEd1YvmW9srdVE88b8"

""" Class """

class YoutubeScraper:

    """ TV shows themes scraper class """

    @staticmethod
    def search(query, limit=1, offset=1):

        """
            Search for a query on YouTube
            ---
            Parameters:
                query : String
                    Query to search
                limit : Integer
                    Number of results to return (default: 1)
                offset : Integer
                    Offset of the results (default: 1)
            ---
            Returns: List
                List of video links and their titles
        """

        print(Fore.YELLOW + f" • Searching for '{query}' on YouTube..." + Style.RESET_ALL)

        # Construct the URL for the search query
        url = f"https://www.youtube.com/results?search_query={query}"

        # Send a GET request to the URL make sure the response is OK
        response = requests.get(url)
        response.raise_for_status()

        # Print the search URL
        print(Fore.YELLOW + f"    - Search url : {url.replace(' ', '%20')}" + Style.RESET_ALL)

        # Parse the HTML content of the response
        soup = BeautifulSoup(response.content, "html.parser")

        # Find all the video links on the search results page
        body = soup.find_all("body")[0]
        scripts = body.find_all("script")

        # Extract the ytInitialData content using regular expressions
        ytInitialData = re.search(r'var ytInitialData\s*=\s*({.*?});', str(scripts))
        
        # If var ytInitialData is found, extract the video links and their titles
        if ytInitialData:
            # Get the matched group containing the ytInitialData object
            ytInitialData_object = ytInitialData.group(1)
            # Parse the object as a dictionary
            ytInitialData_dict = json.loads(ytInitialData_object)
            # Get contents
            scriptsContents = ytInitialData_dict["contents"]

            # Count the number of "itemSectionRenderer" key
            itemSectionRendererEntries = YoutubeScraper.findAllKey(scriptsContents, "itemSectionRenderer")

            # Check if the key is found
            if len(itemSectionRendererEntries) > 0:

                # Try for each "itemSectionRenderer" key
                for itemSectionRenderer in itemSectionRendererEntries:

                    # Get the contents of the key
                    contents = itemSectionRenderer["contents"]

                    # Get an array with "videorenderer" "title" "runs" "text" as "title"
                    # and "videorenderer" "navigationEndpoint" "clickTrackingParams" "commandMetadata" "webCommandMetadata" "url" as "href"
                    videoLinks = [{"title": item["videoRenderer"]["title"]["runs"][0]["text"], "url": item["videoRenderer"]["navigationEndpoint"]["commandMetadata"]["webCommandMetadata"]["url"]} for item in contents if "videoRenderer" in item.keys()]

                    # Add the YouTube domain to the links
                    videoLinks = [{"title": item["title"], "url": f"https://www.youtube.com{item['url']}"} for item in videoLinks]

                    # Apply the limit and offset
                    videoLinks = videoLinks[offset-1:offset-1+limit]

                    # Check if videos are found
                    if len(videoLinks) > 0:
                        # Return the list of video links
                        return videoLinks

            else:
                print(Fore.RED + f"    - Error : itemSectionRenderer not found." + Style.RESET_ALL)
                print(Fore.RED + f"    - Search query : {query}" + Style.RESET_ALL)
        else:
            print(Fore.RED + "    - Error : ytInitialData not found in the string." + Style.RESET_ALL)


        
        # Return an empty list
        return []

    @staticmethod
    #@timeit()
    #@cacheit()
    def searchViaAPI(query, searchType=["video"], count=1, limit=1):

        """ 
            Get the TV show themes
            ---
            Parameters:
                query : String
                    Query to search
            ---
            Returns: List
                List of item search results
        """

        # YouTube API
        api = Api(api_key=YOUTUBE_API_KEY)

        # Search for query
        search_response = api.search_by_keywords(q=query, search_type=searchType, count=count, limit=limit)

        # List of items search results
        items = []

        # Browse the search results
        for item in search_response.items:

            # Add the item to the list
            items.append({
                "id": item.id.videoId,
                "title": item.snippet.title,
                "desc": item.snippet.description,
                "thumbnail": item.snippet.thumbnails.high.url,
                "url": f"https://www.youtube.com/watch?v={item.id.videoId}"
            })

        # Return the list items search results
        return items

    def findAllKey(variable, target_key):
        """
            Find all keys in a dictionary
            ---
            Parameters:
                variable : Dictionary
                    Dictionary to search
                target_key : String
                    Key to find
            ---
            Returns: List
                List of values of the keys
        """
        results = []
        if isinstance(variable, dict):
            if target_key in variable:
                results.append(variable[target_key])
            for value in variable.values():
                results.extend(YoutubeScraper.findAllKey(value, target_key))
        elif isinstance(variable, list):
            for value in variable:
                results.extend(YoutubeScraper.findAllKey(value, target_key))
        return results

    @staticmethod
    def findKey(variable, target_key, occurrence=1):
        """
            Find a key in a dictionary
            ---
            Parameters:
                variable : Dictionary
                    Dictionary to search
                target_key : String
                    Key to find
            ---
            Returns: String/None
                Value of the key or None if not found
        """
        if isinstance(variable, dict):
            if target_key in variable:
                occurrence -= 1
                if occurrence == 0:
                    return variable[target_key]
            for value in variable.values():
                result = YoutubeScraper.findKey(value, target_key, occurrence)
                if result:
                    return result
        elif isinstance(variable, list):
            for value in variable:
                result = YoutubeScraper.findKey(value, target_key, occurrence)
                if result:
                    return result
        return None

    @staticmethod
    def countKey(variable, target_key):
        """
            Count the number of occurrences of a key in a dictionary
            ---
            Parameters:
                variable : Dictionary
                    Dictionary to search
                target_key : String
                    Key to find
            ---
            Returns: Integer
                Number of occurrences of the key
        """
        count = 0
        if isinstance(variable, dict):
            if target_key in variable:
                count += 1
            for value in variable.values():
                count += YoutubeScraper.countKey(value, target_key)
        elif isinstance(variable, list):
            for value in variable:
                count += YoutubeScraper.countKey(value, target_key)

        return count

    @staticmethod
    #@timeit()
    #@cacheit()
    def download(url, videoPath, lengthLimit=None, sizeLimit=None):

        """ 
            Download the video
            ---
            Parameters:
                url : String
                    Video URL
                videoPath : String
                    Path where to save the video
                lengthLimit : Integer
                    Video length limit in seconds (default: None)
                sizeLimit : Integer
                    Video size limit in Mb (default: None)
            ---
            Returns: String
                Downloaded file path
        """

        print(Fore.YELLOW + f" • Downloading '{url}'..." + Style.RESET_ALL)

        # Get path and filename from videoPath
        path, filename = os.path.split(videoPath)

        # Get youtube video
        youtubeVideo = YouTube(url, use_oauth=True, allow_oauth_cache=True)

        # Check video length
        youtubeVideoLength = youtubeVideo.length

        # Check if the video length is less than lengthLimit seconds
        if not lengthLimit or youtubeVideoLength < lengthLimit:

            # Download the video
            #downloadedFilePath = YouTube(url).streams.get_highest_resolution().download(path)

            # Get mp4 format with 720p resolution
            youtubeVideoMP4 = youtubeVideo.streams.filter(progressive=True, file_extension='mp4').get_highest_resolution()

            # Check size of the video in Mb rounded to 2 decimals
            youtubeVideoMP4Size = youtubeVideoMP4.filesize / 1000000

            # Check if the video size is less than sizeLimit Mb
            if not sizeLimit or youtubeVideoMP4Size < sizeLimit:

                # File size in Mb
                print(Fore.YELLOW + f"    - File size : {round(youtubeVideoMP4Size, 2)} Mb" + Style.RESET_ALL)
                    
                # Download the video
                downloadedFilePath = youtubeVideoMP4.download(path, filename)

                # Download file size in Mb
                downloadedFileSize = os.path.getsize(downloadedFilePath) / 1000000

                # Download file path
                print(Fore.YELLOW + "    - Downloaded file path : " + downloadedFilePath + Style.RESET_ALL)

                # Return the downloaded file path
                return downloadedFilePath
            
            else:
                # Convert youtubeVideoMP4Size to Mb
                print(Fore.RED + f"    - Error : Video size is more than {sizeLimit} Mb ({youtubeVideoMP4Size} Mb)." + Style.RESET_ALL)

        else:
            # Convert youtubeVideoLength to minutes and seconds
            print(Fore.RED + f"    - Error : Video length is more than {lengthLimit} seconds ({youtubeVideoLength} seconds)." + Style.RESET_ALL)

        # Return empty string
        return ""

    @staticmethod
    #@timeit()
    #@cacheit()
    def convert3gppToMP4(filePath, debug=False):

        """ 
            Convert 3gpp file to MP4
            ---
            Parameters:
                filePath : String
                    3gpp file path
                debug : Boolean
                    Debug mode
            ---
            Returns: String
                MP4 file path
        """

        # Get the file directory
        fileDir = os.path.dirname(os.path.abspath(filePath))

        # MP4 file path
        mp4FilePath = f"{fileDir}/{filePath.split('/')[-1].split('.')[0]}.mp4"

        # Debug mode
        if debug:
            print(f"MP4 file path : {mp4FilePath}")
            # Convert 3gpp file to MP4 with output (for debugging)
            os.system(f"ffmpeg -i \"{filePath}\" -vcodec copy -acodec copy \"{mp4FilePath}\"")
        else:
            # Convert 3gpp file to MP4
            with open(os.devnull, 'wb') as devnull:
                subprocess.check_call(['ffmpeg', '-i', filePath, '-vcodec', 'copy', '-acodec', 'copy', mp4FilePath], stdout=devnull, stderr=subprocess.STDOUT)

        # Return the MP4 file path
        return mp4FilePath

    @staticmethod
    @timeit()
    #@cacheit()
    def convert3gppToMP3(filePath, debug=False):

        """ 
            Convert 3gpp file to MP3
            ---
            Parameters:
                filePath : String
                    3gpp file path
                debug : Boolean
                    Debug mode
            ---
            Returns: String
                MP3 file path
        """

        # Get the file directory
        fileDir = os.path.dirname(os.path.abspath(filePath))

        # MP3 file path
        mp3FilePath = f"{fileDir}/{filePath.split('/')[-1].split('.')[0]}.mp3"

        # Debug mode
        if debug:
            print(f"MP3 file path : {mp3FilePath}")
            # Convert 3gpp file to MP3 with output (for debugging)
            os.system(f"ffmpeg -i \"{filePath}\" -acodec libmp3lame -ab 128k \"{mp3FilePath}\"")
        else:
            # Convert 3gpp file to MP3
            with open(os.devnull, 'wb') as devnull:
                subprocess.check_call(['ffmpeg', '-i', filePath, '-acodec', 'libmp3lame', '-ab', '128k', mp3FilePath], stdout=devnull, stderr=subprocess.STDOUT)

        # Return the MP3 file path
        return mp3FilePath

    
#####################################################################################################   
#                                            MAIN                                                   #
#####################################################################################################   

# Execute if run as script. 
if __name__ == "__main__":

    # Check if --search argument is passed
    if "--search" in sys.argv:

        # Get the index of --search argument
        searchIndex = sys.argv.index("--search")

        # Get all the arguments passed to the script as query string
        query = " ".join(sys.argv[searchIndex + 1:])

        # Make a search on YouTube
        videoLinks = YoutubeScraper.search(query, limit=5)

        # Print the list of video IDs
        print(videoLinks)
        sys.exit()

    # Check if --download argument is passed
    elif "--download" in sys.argv:
            
        # Get the index of --download argument
        downloadIndex = sys.argv.index("--download")

        # Check if the video URL and video path are passed
        if len(sys.argv) < downloadIndex + 2:
            
            # Ask for the video URL
            videoURL = input("Enter the video URL : ")

            # Trim the video URL
            videoURL = videoURL.strip()

            # Ask for the video path
            videoPath = input("Enter the video path : ")

            # Remove anti-slash from the video path
            videoPath = videoPath.replace("\\", "")

            # Trim the video path
            videoPath = videoPath.strip()

        else:

            # Get the video URL
            videoURL = sys.argv[downloadIndex + 1]

            # Get the video path
            videoPath = sys.argv[downloadIndex + 2]

        # Download the video
        downloadedFilePath = YoutubeScraper.download(videoURL, videoPath)

        # Print the downloaded file path
        print(downloadedFilePath)
        sys.exit()

    else:

        # Print the help message
        print("Usage: python3 YoutubeScraper.py --search <query> | --download <videoURL> <videoPath>")