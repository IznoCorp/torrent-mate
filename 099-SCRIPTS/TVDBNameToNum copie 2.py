#!/usr/bin/env python3 
# -*- coding: utf-8 -*-
#
# Import modules dependancies 
from os import system, listdir, mkdir, rename, execv
from os.path import isfile, isdir, join, basename, splitext
import sys
#from requests import get
#from bs4 import BeautifulSoup
#from unidecode import unidecode
from termcolor import colored
from colorama import init as initColorama
#from tvdb_v4_official import TVDB
from tvdb_api import Tvdb as TVDB # TVDB API v3
# For prompt manipulation
from PyInquirer import prompt
# Inspect library for debug.
import inspect
#
# ! Globals : 
# 
# Text encode type
ENCODAGE = 'utf-8'
# TVDB API key.
#tvdb_api_key = "REDACTED_TVDB_API_KEY"
TVDB_API_KEY = "1b14710f673e899731b462a67307880c"
# TVDB API Pin.
TVDB_API_PIN = "SKTE8HZ5"
# TVDB Language code.
TVDB_LANG_CODE = "en"
# TVDB All Language.
TVDB_ALL_LANG = True
# TVDB DVD Order.
TVDB_DVDORDER = False
# TVDB Interactive choise.
TVDB_INTERACTIVE=False
# TVDB Cache.
TVDB_CACHE=False
# Local TVShows path.
LOCAL_TVSHOW_PATH = "N:/a trier/004 SERIES ANIMATIONS/"
#LOCAL_TVSHOW_PATH = "/Volumes/DISK1/a trier/003 SERIES/"
#
# ! TVDBNameToNum class :
#
class TVDBNameToNum:
  
  """ TVDB script tool to find TV Show episodes season and number based on TV Show episode name. """
  
  def __init__(self):
  
    """ 
      TVDBNameToNum class constructor 
      
      Parameters
      ----------
      
      Returns
      _______
      void
      
    """
    
    # Globals variables :

    # Debug vars.
    self.debug = True
    self.clear_console = True
    self.dry_run = False

    # Local TV Shows list.
    self.local_tvshow_folders = {}
    self.local_tvshows = {}
    # Local TV Shows episodes list to sort.
    self.local_episodes = {}
    
    # TVDB TV Shows list.
    self.tvdb_tvshows = {}
    # TVDB TV Shows episodes list to match.
    self.tvdb_episodes = {}
    
    # Interface vars :
    self.user_input = None 
    self.current_local_tvshow_id = None
    self.current_tvdb_tvshow = None
    self.current_season_num = None
    self.current_episode_num = None 
    self.current_episode_name = None 
    
    # Intefaces Levels
    self.levels = {
      1 : "TVShows",
      2 : "TVShow info",
      3 : "Seasons",
      4 : "Episodes",
      5 : "Episode",
    }
    # Current level.
    self.current_level = 1
    # Current level label.
    self.current_level_label = self.levels[self.current_level]
    
    # ! Initialisation :
    
    # Initialize terminal colors for Windows.
    initColorama()
    
    # Initialize TVDB API with API key.
    self.tvdb_api = TVDB(
      # TVDB API Config :
      apikey = TVDB_API_KEY, 
      language = TVDB_LANG_CODE,
      search_all_languages = TVDB_ALL_LANG,
      interactive = TVDB_INTERACTIVE,
      dvdorder = TVDB_DVDORDER,
      cache = TVDB_CACHE,
    )
    
    # ! Interface
    
    # Choose process session.
    self.launchSession()
    
    # End.
    return
  
  # ! Utility methods :  
  
  def printError(self, error_message):
    
    """
      Print error in red, and wait for user confirmation to continue.
      ---
      Params
        error_message : String
          Message to show.
      ---
      Return : None
    """
    
    # [DEBUG]
    print(colored(f"{error_message}", "red"))
    # [WAIT]
    wait = input("Press any key to continue...")
    # Return
    return None
  
  def clearConsole(self):
    """ 
      Cleaning method for the console.
    """

    # If clear console debug is true.
    if self.clear_console == True :
      # Clear console.
      system('cls')
  
  # ! Generic path method :
  
  def getFoldersNames(self, local_path, recursive=None):
    
    """ 
      Retrieve list sub-folders names in a local disks folder.
       
      Parameters
      ----------
      local_path : String
        Absolute path to a local folder.
        
      Returns
      _______
      local_folders : Dict [local_folder_id : local_folder_name]
        A list that contains folders names.
    """
    
    # Retrieve folders names from local_path
    local_folders_list = [local_folder for local_folder in listdir(local_path) if isdir(local_path+local_folder)]
    
    # Create local TVShow ID for each folder.
    local_folder_id = 1
    # Create a local folders dict.
    local_folders = {}
    for local_folder_name in local_folders_list : 
      # Add a position to eatch local folder.
      local_folders[local_folder_id] = local_folder_name
      # Increase local_folder_id
      local_folder_id += 1
      
    # Return
    return local_folders
    
  def getFilesNames(self, local_path, recursive=None):
    
    """ 
      Retrieve list of files in a local disks folder.
      
      Returned dict format : 
      {
        path : file_path, 
        basename : file_basename, 
        name = file_name, 
        size = file_size
      }
       
      Parameters
      ----------
      local_path : String
        Absolute path to a local folder.
        
      Returns
      _______
      local_files : Dict {path : file_path, basename : file_basename, name = file_name, size = file_size}
        A dict that contains files informations.
    """
    
    # Retrieve files names from local_path
    local_files = [local_file for local_file in listdir(local_path) if isfile(local_path+local_file)]
    
    # Return
    return local_files
    
  # ! Local path methods : 
  
  def getLocalCurrentTVShowPath(self):
    
    """
      Return current TVShow path if exist, None if not.
      ---
      Return String | None
        Correct current TVShow local path. None if there is no path found.
    """
    
     
    # Retrieve local TVShow folder. 
    local_tvshow_folder = self.local_tvshow_folders[self.current_local_tvshow_id]
    # Define local TVShow path. 
    local_tvshow_path = f"{LOCAL_TVSHOW_PATH}{local_tvshow_folder}/"
    # Check if local_tvshow_path exist.
    if isdir(local_tvshow_path) :
      return local_tvshow_path
    else:
      return None
    
  
  def getLocalSeasonPath(self, season_number):
    
    """
      Check if season path of current TVShow exist in local.
      Check for multiple possible format of path.
      Return the correct path format.
      ---
      Parameters
        season_number : Int
          Number of the season to check.
      ---
      Return String | None
        Correct current TVShow and season path. None if there is no path found.
    """
    
    # Retrieve current local TVShow path.
    current_tvshow_path = self.getLocalCurrentTVShowPath()
    
    # Retrieve local seasons folders.
    seasons_folders = self.getFoldersNames(current_tvshow_path)
       
    # Check if selected tvshow folder exist.
    if current_tvshow_path is None : 
      # Return
      return None
    
    # Variables for possibilities.
    season_number1 = str(season_number).zfill(1)
    season_number2 = str(season_number).zfill(2)
    
    # Season names possibilities.
    season_strings = []
    
    season_strings.append(f"saison {season_number1}")
    season_strings.append(f"saison {season_number2}")
    season_strings.append(f"saison{season_number1}")
    season_strings.append(f"saison{season_number2}")
    
    season_strings.append(f"s {season_number1}")
    season_strings.append(f"s {season_number2}")
    season_strings.append(f"s{season_number1}")
    season_strings.append(f"s{season_number2}")
        
    # Check all possibilities.
    for season_string in season_strings :
      # In local season paths.
      for season_index, season_folder in seasons_folders.items():
        # Check if local season folder contains a season_string
        if season_string.lower() in season_folder.lower() :
          # Create season path.
          season_path = f"{current_tvshow_path}{season_folder}/"
          # Return season_path.
          return season_path
          
    
    # Return None.
    return None
    
  def renameTVShow(self, local_tvshow_index, tvdb_tvshow):
    
    """
      Rename a local TVShow folder, to match a TVDB TVShow name.
      ---
      Parameters
        local_tvshow_index : Int
          TVShow local folder index.
        tvdb_tvshow : Object (TVDB TVShow API Object)
          TVDB TVShow API Object.
      
      ---
      Return Boolean : Episode have been renamed.
    """
    
    # Retrieve local TVShow folder name.
    local_tvshow_folder_name = self.local_tvshow_folders[local_tvshow_index]
    
    # Retrieve infos for renaming.
    tvdb_tvshow_name = tvdb_tvshow['seriesName']
    
    # Define old and new folders names.
    old_tvshow_folder_name = f"{local_tvshow_folder_name}"
    new_tvshow_folder_name = f"{tvdb_tvshow_name}"
    
    # Define old and new paths.
    old_tvshow_path = f"{LOCAL_TVSHOW_PATH}{old_tvshow_folder_name}"
    new_tvshow_path = f"{LOCAL_TVSHOW_PATH}{new_tvshow_folder_name}"
    
    # Dry Run ?
    if self.dry_run :
      print(f"rename({old_tvshow_path}, {new_tvshow_path})")
      input("Press any key to continue...")
    else:
      # Rename local tvshow folder.
      if rename(old_tvshow_path, new_tvshow_path) : 
        # If rename done change local dict value.
        self.local_tvshow_folders[local_tvshow_index] = new_tvshow_folder_name
        # Return
        return True
    
    # Return
    return False
    
  def renameEpisode(self, episode_file_name, tvdb_episode) :
    
    """
      Rename a local episode file, to match a TVDB episode.
      ---
      Parameters
        episode_file_name : String
          Episode local file name.
        tvdb_episode : Object (TVDB TVShow Episode API Object)
          TVDB Episode API Object.
      
      ---
      Return Boolean : Episode have been renamed.
    """
    
    # Retrieve infos for renaming :
    
    # Current TVShow path.
    current_tvshow_path = self.getLocalCurrentTVShowPath()
    
    # Current season path.
    current_season_path = self.getLocalSeasonPath(self.current_season_num)
    
    # Check season path.
    if current_season_path is None :
      # Return
      return False
    
    # Local episode infos.
    local_episode_file_name = splitext(episode_file_name)[0]
    local_episode_file_ext = splitext(episode_file_name)[1]
    
    # TVDB episode infos.
    tvdb_episode_name = tvdb_episode['episodeName']
    tvdb_episode_num = tvdb_episode['airedEpisodeNumber']
    tvdb_season_num = tvdb_episode['airedSeason']
    tvdb_episode_num_str = str(tvdb_episode_num).zfill(2)
    tvdb_season_num_str = str(tvdb_season_num).zfill(2)
    
    # Define new season folder and check if exist.
    new_season_path = f"{current_tvshow_path}Saison {tvdb_season_num_str}/"
    if not isdir(new_season_path) :
      mkdir(new_season_path)
    
    # Define renaming names and paths :
    
    # Define old and new names.
    old_episode_name = f"{episode_file_name}"
    new_episode_name = f"S{tvdb_season_num_str}E{tvdb_episode_num_str} - {tvdb_episode_name}{local_episode_file_ext}"
    
    # Define old and new paths.
    old_episode_path = f"{current_season_path}{old_episode_name}"
    new_episode_path = f"{current_tvshow_path}Saison {tvdb_season_num_str}/{new_episode_name}"
    
    # Dry run ?
    if self.dry_run :
      print(f"rename({old_episode_path}, {new_episode_path})")
      input("Press any key to continue...")
    else :
      # Rename local episode file.
      if rename(old_episode_path, new_episode_path) : 
        return True
     
    # End  
    return False
    
  def checkEpisodeName(self, name1, name2):
    
    """
      Check if name1 and name2 may be the same.
      
      ---
      Return Boolean : True if name matched. False otherwise.
    """
      
    # Check if name1 match name2
    if name1.strip().lower() in name2.strip().lower() or name2.strip().lower() in name1.strip().lower() :
      return True
    else:
      return False

  
  # ! TVDB API :
  
  def getTVDBShows(self):
    
    """ 
      Retrieve self.local_tvshow_folders TV Show informations from TVDB API.
        
      Returns
      _______
      None
    """
    
    # For eatch tvshow names.
    for local_tvshow_id, local_tvshow_folder_name in self.local_tvshow_folders.items() :
      
      # Try to retrieve the tvshow via TVDB API
      tvdb_tvshow = self.getTVDBTVShow(local_tvshow_id)
      # If TVShow if found.
      if tvdb_tvshow is not None :
        # Add TVShow to list.
        self.tvdb_tvshows[local_tvshow_id] = tvdb_tvshow
      
    # Return.
    return None
      
  def getTVDBTVShow(self, local_tvshow_index):
    
    """ 
      Try to match a local TV Show name to TVDB TV Show name.
      Return a list of TVDB TV Shows name, empty if no match, 1 entry if a match is found, multiple entries if multiple match found.
       
      Parameters
      ----------
      local_tvshow_index : Int
        Local TV Show folder index
        
      Returns
      _______
      tvdb_tvshow : Object (TVDB TVShow API Object)
        A TVDB TVShow API Object that contains all TVShow info, seasons and episodes.
    """
    
    # Retrieve local TVShow folder name.
    local_tvshow_folder_name = self.local_tvshow_folders[local_tvshow_index]
    
    # Search name.
    search_name = local_tvshow_folder_name
    
    # Skip TVShow flag.
    skip_tvshow = False
    
    # Define var for TVDB TVShow.
    tvdb_tvshow = None
    
    # Search for TVShow while not found or not skip.
    while tvdb_tvshow is None and skip_tvshow is False :
      
      # Retrieve a tvshow by search_name via TVDB API.
      try:
        tvdb_tvshow = self.tvdb_api[search_name]
      except:
        pass
        
      # Check if TVShow found on TVDB.
      if tvdb_tvshow is not None :
        
        # If search_name is not the original local_tvshow_folder_name.
        if search_name != local_tvshow_folder_name:
          
           # Ask if user want to rename the tvshow folder.
          # Choose what to process : 
          possibilities = {}
          possibilities[0] = "Ne pas renommer."
          possibilities[1] = "Renommer le dossier de série."
      
          # Ask user to select a season number.
          possibility_index = self.checkUserInput(possibilities, f"'{search_name}' à trouvé une correspondance avec : '{tvdb_tvshow}'. Souhaitez-vous renommer le dossier de série ?") 
          # Check answer
          if possibility_index == 1 :
            # Rename the TVShow folder.
            self.renameTVShow(local_tvshow_index, tvdb_tvshow)
            # [DEBUG]
            input('wait')
            
        # Return a TVDB TVShow Object.
        return tvdb_tvshow
        
      else:
        
        # Ask if user want to search with another name.
        # Choose what to process : 
        possibilities = {}
        possibilities[0] = "Passer la série."
        possibilities[1] = "Relancer une recherche."
    
        # Ask user to select a season number.
        possibility_index = self.checkUserInput(possibilities, f"La série {search_name} n'a pu être trouvé sur TVDB, souhaitez-vous la chercher à l'aide d'un autre nom ?") 
        # Check answer
        if possibility_index == 1 :
          
          # User search modification, ask user to update tvshow label.
          question = [
            {
              'type': 'input',
              'name': 'search_name',
              'message': 'Entrer un nouveau nom pour la recherche : ',
              'default': search_name
            }
          ]
          # Retrieve answer.
          answer = prompt(question)
          # Retrieve search_name from answer.
          search_name = answer['search_name']
                    
        else:
          # Skip TVShow
          skip_tvshow = True
    
    return None
    

  # ! Interface methods :
  
  def launchSession(self):
    
    """ 
      Launch a TVDB sorting process session.
       
      Parameters
      ----------

      Returns
      _______
      None
    """
    
    # Pre-processing local folder :
        
    # Retrieve local tvshow folders dict.
    self.local_tvshow_folders = self.getFoldersNames(LOCAL_TVSHOW_PATH)
    # [DEBUG]
    if self.debug :
      #print(self.local_tvshow_folders)
      pass
    
    # Retrieve TVDB tvshow dict.
    self.getTVDBShows()
    # [DEBUG]
    if self.debug :
      #print(self.tvdb_tvshows)
      pass
    
    # ! Clearing the console.
    self.clearConsole()
    
    # Interface loop.
    while True :      
        
      # ! Choose function to play depending on interface level : 
        
      # ! - TVShows.
      if self.current_level == 1 : 
        # Choose TVDB TVShow to process.
        self.chooseTVShow()
      # ! - TVShows infos.
      elif self.current_level == 2 :
        # Choose TVShow infos to display.
        self.chooseTVDBTVShowInfos()
      # ! - Seasons.
      elif self.current_level == 3 :
        # Choose season number to display episode list.
        self.chooseTVShowSeason()
      # ! - Episodes.
      elif self.current_level == 4 :
        # Get All TVDB Episodes.
        self.getAllTVDBEpisodes()
        # Choose episode number to display infos.
        self.chooseTVShowEpisodes()
      elif self.current_level == 5 :
        # Search for matching episode on TVDB.
        self.searchForEpisodeNameOnTVDB()
        
      # ! Clearing the console.
      self.clearConsole()
      
      # ! Switch on interface level : 
      
      # [DEBUG]
      if self.debug :
        #print(f"User input : {self.user_input}")
        pass
        
      # ! - Interface level rewind.
      if self.user_input == 0 :
        # Check if rewind possible.
        try:
          self.current_level_label = self.levels[self.current_level-1]
          self.current_level = self.current_level - 1
        except:
          print(f"Error can't rewind interface level.")
        # Reset user_input value.
        self.user_input = None
      # ! - Interface level increase.
      else:
        # Check if increase possible.
        try:
          self.current_level_label = self.levels[self.current_level+1]
          self.current_level = self.current_level + 1
        except:
          print(f"Error can't increase interface level.")
            
      
    
    # [DEBUG]
    if self.debug :
      input("--- Fin de programme ---")   
      
      
    # Return
    return None
  
  
  def checkUserInput(self, possibilities, input_question = "Choisissez une valeur : ", possibility_label = "", possibilities_colors = None):
    
    """ 
      Ask user to enter a index value in a possible dict.
      Control the input and return index.
       
      Parameters
      ----------
      possibilities : Dict
        Possible input values dict {index : possible input value}
      input_question : String
        Input prompt string value.
      possibility_label : String
        Possibility label name.
      possibilities_colors : Dict [default = None]
        Dict that contain string print color for possibility if needed.
        
      Returns
      _______
      input_index : Int
        Index of the input possibility. 
    """ 
    
    # Reset user_input.
    self.user_input = None
    
    # Formating & prompt.
    print(f"")
    print(f"{input_question}")
    print(f"")
    
    # Showing possibilities.
    for possibility_index, possibility_value in possibilities.items() :
      # Check for possibility print color.
      try :
        # Retrieve color.
        print_color = possibilities_colors[possibility_index]
        # Print with color.
        print(colored(f"#{possibility_index} : {possibility_label} {possibility_value}", print_color))
      except:
        # Print without color.
        print(f"#{possibility_index} : {possibility_label} {possibility_value}")
    
    # List of possible index.
    possibilities_indexs = list(possibilities.keys()) 
    
    # Check if rewind possible.
    try:
      self.current_level_label = self.levels[self.current_level-1]
      # Show return index.
      print(f"")
      print(f"#0 : Retour")
      # Add "Return" index 0
      possibilities_indexs.append(0)
    except:
      pass 
      
    # Check user input in possibilities.
    while self.user_input not in possibilities_indexs :
      
      # Check previous input error.
      if self.user_input is not None :
        print(f"Index incorrect.")
      
      # Asking for a choice
      print(f"")
      self.user_input = input(f" ? => ")
      
      # Check if input is int.
      try:
        self.user_input = int(self.user_input.strip())
      except:
        print(f"Saisie incorrect.")
        
    # Return input_index.
    return self.user_input
      
  
  def chooseTVShow(self):
    
    """ 
      Print TVDB TVShow list (self.tvdb_tvshows) for process choice.
       
      Returns
      _______
      None.
    """
        
    # Create local tvshow ids list to verify user input.
    local_tvshow_ids = []
    
    # Ask user to select a season number.
    self.current_local_tvshow_id = self.checkUserInput(self.tvdb_tvshows, "Choisissez une série à traiter ?")
    # Retrieve choosen TVDB TVShow.
    try:
      self.current_tvdb_tvshow = self.tvdb_tvshows[self.current_local_tvshow_id]
    except:
      pass
    
    # Return
    return None
  
  
  def chooseTVDBTVShowInfos(self):
    
    """ 
      Print TVDB TVShow information for process choice.
       
      Parameters
      ----------
      tvdb_tvshow : TVDBTVShow
        TVDB TVShow object
        
      Returns
      _______
      user_input : String
    """
    
    # Retrieving TVDB TVShow infos :
    tvdb_tvshow_id = self.current_tvdb_tvshow.data['id']
    #tvdb_tvshow_id2 = tvdb_tvshow.data['seriesId']
    tvdb_tvshow_imdb_id = self.current_tvdb_tvshow.data['imdbId']
    tvdb_tvshow_name = self.current_tvdb_tvshow.data['seriesName']
    tvdb_tvshow_aliases = self.current_tvdb_tvshow.data['aliases']
    tvdb_tvshow_status = self.current_tvdb_tvshow.data['status']
    tvdb_tvshow_network = self.current_tvdb_tvshow.data['network']
    tvdb_tvshow_season = self.current_tvdb_tvshow.data['season']
    tvdb_tvshow_language = self.current_tvdb_tvshow.data['language']
    tvdb_tvshow_overview = self.current_tvdb_tvshow.data['overview']
    #tvdb_tvshow_last_updated = tvdb_tvshow.data['lastUpdated']
    #tvdb_tvshow_rating = tvdb_tvshow.data['rating']
    tvdb_tvshow_site_rating = self.current_tvdb_tvshow.data['siteRating']
    tvdb_tvshow_site_rating_count = self.current_tvdb_tvshow.data['siteRatingCount']
    
    # Print TVShow info : 
    
    # Formating.
    print("")
    # TVDB Show name.
    print(f"#{tvdb_tvshow_id} : {tvdb_tvshow_name} [{tvdb_tvshow_network}]")
    if tvdb_tvshow_aliases :
      print(f"Aliases : {tvdb_tvshow_aliases}")
    print(f"Identifiant TVDB : #{tvdb_tvshow_id}") 
    print(f"Identifiant IMDB : #{tvdb_tvshow_imdb_id}")
    print(f"Status : {tvdb_tvshow_status}")
    print(f"Saisons : {tvdb_tvshow_season}")
    print(f"Langue : {tvdb_tvshow_language}")
    print(f"Résumé : {tvdb_tvshow_overview}")
    print(f"Note : {tvdb_tvshow_site_rating} pour {tvdb_tvshow_site_rating_count} votes.")
    
    # Choose what to process : 
    possibilities = {}
    possibilities[1] = "Voir la liste des saisons disponible."
    
    # Ask user to select a season number.
    possibility_index = self.checkUserInput(possibilities)
    
    # Return
    return possibility_index
    
    
  def chooseTVShowSeason(self):
    
    """ 
      Print TVDB TVShow season list for process choice.
        
      Returns
      _______
      None
    """
    
    # Choose season to process : 
    
    # Number of seasons.
    tvdb_tvshow_seasons_count = self.current_tvdb_tvshow.data["season"]
    
    # [DEBUG]
    if self.debug :
      #print(f"Number of season : {int(tvdb_tvshow_seasons_count)}")
      pass
      
    # Retrieve seasons in dict.
    season_numbers = {}
    season_numbers_colors = {}
    
    # For each TVDB TVShow.
    for season_number in self.current_tvdb_tvshow.keys() :
      # Check if season exist in TVShow folder.
      local_season_path = self.getLocalSeasonPath(season_number)
      if local_season_path is not None :
        # Add season to list.
        season_numbers[season_number] = season_number
        # Show season in green.
        season_numbers_colors[season_number] = "green"
        
    # Check for classique local season
    classic_seasons_numbers = range(1, 10)
    
    # Check classic seasons too. 
    for classic_season_number in classic_seasons_numbers :
      # If season doesn't exist yet.
      try:
        season_numbers[classic_season_number] 
      except:
        # Check if season exist in TVShow folder.
        local_season_path = self.getLocalSeasonPath(classic_season_number)
        if local_season_path is not None :
          # Add season to list.
          season_numbers[classic_season_number] = classic_season_number
          # Show season in green.
          season_numbers_colors[classic_season_number] = "yellow"
        
    
    # Ask user to select a season number.
    self.current_season_num = self.checkUserInput(season_numbers, "Choisissez une saison à afficher : ", "saison")
    
    # Return.
    return None
  
  def chooseTVShowEpisodes(self):
    
    """ 
      Print Local TVShow season episodes list for process choice.
    """
    
    # Retrieve local current TVShow path.
    local_tvshow_path = self.getLocalCurrentTVShowPath()
      
    # Check if selected tvshow folder exist.
    if local_tvshow_path is None :
      # Retrieve local tvshow folder name.
      local_tvshow_folder = self.local_tvshow_folders[self.current_local_tvshow_id]
      # [DEBUG] Print error message.
      self.printError("Aucun dossier ne correspond pour la série. Le dossier '{local_tvshow_folder}' n'existe pas.")
      # Ask for return to season menu.
      self.user_input = 0
      # Exit method.
      return None
    else:
      # [DEBUG]
      if self.debug : 
        print(colored(f"Dossier saison trouvé : {local_tvshow_path}", "green"))
    
    # Get current season path.
    local_season_path = self.getLocalSeasonPath(self.current_season_num) 
    
    # Check if selected season folder exist.
    if local_season_path is None :
      # [DEBUG] Print error message.
      self.printError(f"Aucun dossier ne correspond pour la saison. Le dossier  de la Saison '{self.current_season_num}' n'existe pas.")
      # Ask for return to season menu.
      self.user_input = 0
      # Exit method.
      return None
    else:
      # [DEBUG]
      if self.debug : 
        print(colored(f"Dossier saison trouvé : {local_season_path}", "green"))
    
    
    # Retrieve episodes files names from current_season_folder
    local_episodes_list = self.getFilesNames(local_season_path)
    
    # Create episode dict
    index = 1
    local_episode_dict = {}
    local_episode_color_dict = {}
    for episode_file_name in local_episodes_list :
      local_episode_dict[index] = episode_file_name
      if self.macthTVDB(episode_file_name) : 
        # Match episode show in green.
        local_episode_color_dict[index] = "green"
      else:
        # No match episode shox in yellow
        local_episode_color_dict[index] = "yellow"
      # Increase index.
      index = index + 1
    
    # Ask user to select a episode.
    episode_number_index = self.checkUserInput(local_episode_dict, "Choisissez un episode à traiter : ", None, local_episode_color_dict)
    
    # Retrieve episode file name to treat.
    if episode_number_index != 0 :
      self.current_episode_name = local_episode_dict[episode_number_index]
    
    # END !
    return None
    
  
  def getAllTVDBEpisodes(self):
    
    # ! TVDB Episodes : 
      
    # Loop over all seasons.
    for season_number in self.current_tvdb_tvshow.keys() :
      # Retrieve season.
      season = self.current_tvdb_tvshow[season_number]
      # Check first 1000 episode. (stop when season episode doesn't exist)
      for episode_number in season.keys() :
        # Retrieve episode.
        self.tvdb_episodes[(season_number, episode_number)] = season[episode_number]
        
    # Return
    return None
        
  
  def macthTVDB(self, local_episode_name):
    
    """
      Check if local episode name match a TVDB episode name.
      ---
      Parameters
        local_episode_name : String
          local episode name
      ---
      Return 
        Boolean : episode find in TVDB episodes list.
      
    """
        
    # ! Compare episode search to TVDB Episode list.
    
    # Check for all TVDB episode.
    for tvdb_episode_infos, tvdb_episode in self.tvdb_episodes.items() :
      # Retrieve TVDB Episode name.
      tvdb_episode_name = tvdb_episode['episodeName']
      # Compare TVDB episode name with searched episode name.
      if self.checkEpisodeName(tvdb_episode_name, local_episode_name) :
        return True
        
    # Return
    return False
        
    
  
  def searchForEpisodeNameOnTVDB(self):
    
    """ 
      Search TVShow episode name in TVDB TVShow episodes list.
    """
    
    # Episode name that will be searched.
    local_episode_name = splitext(self.current_episode_name)[0]
    local_episode_ext = splitext(self.current_episode_name)[1]
    
    # User search modification, ask user to update episode label if needed.
    question = [
      {
        'type': 'input',
        'name': 'episode_name',
        'message': 'Nom de l\'épisode à traiter : ',
        'default': local_episode_name
      }
    ]
    answer = prompt(question)
    local_episode_name = answer['episode_name']    
    print(colored(f"Recherche pour '{local_episode_name}' ... ", "yellow"))
    
    
    # ! Compare episode search to TVDB Episode list.
    
    # List of matched episodes.
    matched_episodes   =  {}
    matched_episodes_names = {} 
    # List of matched episodes count.
    matched_episode_count   =  0
    # Check for all TVDB episode.
    for tvdb_episode_infos, tvdb_episode in self.tvdb_episodes.items() :
      # Retrieve episode infos.
      tvdb_episode_name = tvdb_episode['episodeName']
      tvdb_episode_num = tvdb_episode_infos[1]
      tvdb_season_num = tvdb_episode_infos[0]
      # Compare TVDB episode name with searched episode name.
      if self.checkEpisodeName(tvdb_episode_name, local_episode_name) :
        # Increase matched episode count.
        matched_episode_count = matched_episode_count + 1
        # Save matched episode.
        matched_episodes[matched_episode_count] = tvdb_episode        
        # Add episode name to matched_episode_names
        matched_episodes_names[matched_episode_count] = f"S{str(tvdb_season_num).zfill(2)}E{str(tvdb_episode_num).zfill(2)} - {tvdb_episode_name}"
    
    # Show list of matched episode.
    if len(matched_episodes) > 0 :
      
      # If more than 1 match episode found.
      if len(matched_episodes) > 1 :
        # Ask user to select a episode.
        matched_episode_index = self.checkUserInput(matched_episodes_names, "Choisissez l'épisode qui correspond : ")
      else:
        # Considered episode found as the user choice.
        matched_episode_index = 1
      
      # Retrieve matched episode.
      matched_episode = matched_episodes[matched_episode_index]
      matched_episode_name = matched_episodes_names[matched_episode_index]
      
      # Show matched episode rename.
      print(f"Souhaitez-vous renommer l'épisode : ")
      print(colored(f"  '{self.current_episode_name}'", "yellow"))
      print(f" en : ")
      print(colored(f"  '{matched_episode_name}{local_episode_ext}'", "green"))
      print(f" ? ")
      
      # Choose what to process : 
      possibilities = {}
      possibilities[1] = "Renommer."
      
      # Ask user to select a season number.
      possibility_index = self.checkUserInput(possibilities)

      # Renaming
      if possibility_index == 1 :
        # Rename episode.
        self.renameEpisode(self.current_episode_name, matched_episode)
      
    else:
      # [DEBUG]
      self.printError(f"Aucun épisode trouvé sur TVDB.")
    
    # Rewind interface level.
    self.user_input = 0
    
    # Return
    return None
    
  
  
#####################################################################################################   
#                                            MAIN                                                   #
#####################################################################################################   

# ! Main  :

# Execute if run as script. 
if __name__ == "__main__":
  
  '''Main executed code, for script call.'''
  
  # Create TVDBNameToNum session.
  TVDB_session = TVDBNameToNum()
  
  # 
  
  
  