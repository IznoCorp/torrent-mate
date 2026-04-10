#!/usr/bin/env python
# -*- coding: utf-8 -*-
#

""" Importing libraries """

import os
import shutil
from decorators import timeit, cacheit

""" Class """
class FileSystem:

    """ FileSystem management class """

    @staticmethod
    #@timeit()
    @cacheit()
    def getSubFolders(paths):

        """ 
            Get the list of movies folders
            ---
            Parameters:
                paths : List
                    List of movies paths
            ---
            Returns: List
                List of movies folders
        """
        
        # Sub-folders list
        subFolders = []

        # Browse the paths
        for path in paths :

            # Check if the path exists
            if not os.path.exists(path) :
                # Print the path does not exist
                print(f"WARNING : Folder does not exist : {path}")
                # Continue to the next path
                continue

            # Get folders in the path.
            folders = [os.path.join(path, dirname) for dirname in os.listdir(path) if os.path.isdir(os.path.join(path, dirname))]

            # Add folders to the sub-folders list
            subFolders.extend(folders)

        # Return the sub-folders list
        return subFolders

    @staticmethod
    @timeit()
    @cacheit() 
    def getEmptyFolders(folders, extensions):

        """ 
            Get the list of empty TV shows folders 
            ---
            Parameters:
                folders : List
                    List of TV shows folders
                extensions : List
                    List of file extensions
            ---
            Returns: List
                List of empty TV shows folders
        """

        # Empty TV shows folders list
        emptyFolders = [folder for folder in folders if not FileSystem.checkForFiles(folder, extensions)]

        # Return the empty folders list
        return emptyFolders
    
    @staticmethod
    def checkForFiles(path, extensions):

        """ 
            Check if there file  in the folder 
            ---
            Parameters:
                path: String
                    Path to the folder
                extensions: List
                    List of file extensions
            ---
            Returns: Boolean
                True if there is a video file in the folder
                False if there is no video file in the folder
        """

        # Add the path to paths to check.
        pathsToCheck = [path]

        # Add all subfolders that don't start with '.' to the paths to check.
        pathsToCheck.extend([os.path.join(path, dirname) for dirname in os.listdir(path) if os.path.isdir(os.path.join(path, dirname)) and not dirname.startswith('.')])

        # Browse the paths to check
        for pathToCheck in pathsToCheck :
            # If there is a video file in the folder
            if FileSystem.hasFiles(pathToCheck, extensions) :
                # Return True
                return True

        # Return False
        return False

    @staticmethod
    @cacheit() 
    def hasFiles(path, extensions):

        """ 
            Check if there is a file with matching extensions in the folder
            ---
            Parameters:
                path: String 
                    Path to the folder
                extensions: List
                    List of file extensions
            ---
            Returns: Boolean
                True if there is a video file in the folder
        """

        # Get matching files in the path.
        matchingFiles = [os.path.join(path, filename) for filename in os.listdir(path) if os.path.isfile(os.path.join(path, filename)) and os.path.splitext(filename)[1].lower() in extensions]

        # If matching files detected
        if len(matchingFiles) > 0 :
                
            # Return True
            return True
        
        # If no video files detected    
        else:
                
            # Return False
            return False

    @staticmethod
    def removeFolders(folders, dryRun = True):

        """ 
            Delete folders and files from the filesystem.
            ---
            Parameters:
                emptyFolders: List
                    List of empty folders
        """

        # Browse the folders
        for folder in folders :
            # If dry run.
            if dryRun :
                # Print the folder to delete
                print(f"[DRY RUN] Folder to delete: \"{folder}\"")
            else:
                # Print the folder to delete
                print(f"Deleting folder : \"{folder}\"")
                # Check if the folder exists
                if os.path.exists(folder) :                    
                    # Delete the folder
                    shutil.rmtree(folder)
                    # Check if the folder has been deleted
                    if os.path.exists(folder) :
                        # Print the folder not deleted
                        print(" - Error folder not deleted")
                    else :
                        # Print the folder deleted
                        print(" - Folder deleted")
                else :
                    # Print the folder does not exist
                    print(" - Folder does not exist")