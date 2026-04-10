#!/usr/bin/env python3 
# -*- coding: utf-8 -*-
#
# Import modules dependancies 
from os import system, listdir, mkdir, rename
from os.path import isfile, isdir, join, basename, splitext
#from requests import get
#from bs4 import BeautifulSoup
#from unidecode import unidecode
from termcolor import colored
from colorama import init as initColorama
#from tvdb_v4_official import TVDB
from tvdb_api import Tvdb as TVDB # TVDB API v3
#
# ! Globals : 
# 
# Text encode type
Encodage = 'utf-8'
# TVDB API key.
#tvdb_api_key = "REDACTED_TVDB_API_KEY"
tvdb_api_key = "1b14710f673e899731b462a67307880c"
# TVDB API Pin.
tvdb_api_pin = "SKTE8HZ5"
# TVDB Language code.
tvdb_language_code = "en"
# TVDB All Language.
tvdb_all_languages = True
# TVDB DVD Order.
tvdb_dvdorder = False
# TVDB Interactive choise.
tvdb_interactive=False
# TVDB Cache.
tvdb_cache=False
# Local TVShows path.
local_tvshows_path = "N:/a trier/003 SERIES/"
#local_tvshows_path = "/Volumes/DISK1/a trier/003 SERIES/"
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
    
    # Local TV Shows list.
    self.local_tvshows = {}
    # Local TV Shows episodes list to sort.
    self.local_episodes = {}
    
    # TVDB TV Shows list.
    self.tvdb_tvshows = {}
    # TVDB TV Shows episodes list to match.
    self.tvdb_episodes = {}
    
    # Interface vars :
    self.user_choice = None 
    self.current_local_tvshow_id = None
    self.current_tvdb_tvshow = None
    self.current_season_num = None
    self.current_episode_num = None 
    
    # ! Initialisation :
    
    # Initialize terminal colors for Windows.
    initColorama()
    
    # Initialize TVDB API with API key.
    self.tvdb_api = TVDB(
      # TVDB API Config :
      apikey = tvdb_api_key, 
      language = tvdb_language_code,
      search_all_languages = tvdb_all_languages,
      interactive = tvdb_interactive,
      dvdorder = tvdb_dvdorder,
      cache = tvdb_cache,
    )
    
    # Creating a cleaning method for the console.
    self.clearConsole = lambda: system('cls')
    
    # ! Interface
    
    # Choose process session.
    self.launchSession()
    
    # End.
    return
  
  # ! Utility methods :  
  
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
    
    return local_files
  
  # ! Local tvshows methods :
  
  def getLocalTVShows(self, local_tvshows_path):
    
    """ 
      Retrieve list of TV Shows in a local disks folder.
       
      Parameters
      ----------
      local_tvshows_path : String
        Absolute path to the tv shows local folder.
        
      Returns
      _______
      local_tvshows : Dict {local_tvshow_path : local_tvshow_name}
        A list that contains the local tvshows names.
    """
    
    # Retrieve local tvshow list.
    local_tvshows = self.getFoldersNames(local_tvshows_path)
    
    return local_tvshows
    
  def getLocalSeason(self, local_tvshow_path):
    
    """ 
      Retrieve local disks informations on seasons folders.
       
      Parameters
      ----------
      local_tvshow_path : String
        Absolute path to a tv show local folder.
        
      Returns
      _______
      local_tvshow_seasons : List [season_number]
        A list that contains the local tvshow seasons.
    """
    
    return local_tvshow_seasons
    
  def getLocalEpisodes(self, local_tvshow_path, season_number=None):
    
    """ 
      Retrieve local disks informations on episodes files for a tvshow path.
       
      Parameters
      ----------
      local_tvshow_path : String
        Absolute path to a tv show local folder.
      season_number (optionnal) : Int
        Number of the season. [Default = None]
        
      Returns
      _______
      local_tvshow_episodes : Dict {local_episode_path : local_episode_name}
        A dict that contains the names of the local tvshow episodes.
    """
    
    return local_tvshow_episodes
  
  # ! TVDB shows methods :
  
  def getTVDBShows(self, local_tvshow_names):
    
    """ 
      Retrieve TV Show informations from TVDB API.
       
      Parameters
      ----------
      local_tvshow_names : List [folder_name]
        Tvshow list of names.
        
      Returns
      _______
      tvdb_tvshows : Dict {local_tvshow_id : tvdb_tvshow}
        A dict that contains the TVDB show list.
    """
    
    # Create a tvshow names dict.
    tvdb_tvshows = {}
    # For eatch tvshow names.
    for local_tvshow_id, local_tvshow_name in local_tvshow_names.items() :
      
      try:
        # Retrieve a tvshow by name.
        tvdb_tvshow = self.tvdb_api[local_tvshow_name]
        # Add tvshow to tvdb list of tvshow names.
        tvdb_tvshows[local_tvshow_id] = tvdb_tvshow
      except:
        # [DEBUG]
        print(f"Show named '{local_tvshow_name}' not found on TVDB API.")
        wait = input("PRESS ENTER TO CONTINUE.")
      
    # Return.
    return tvdb_tvshows
  
  def getTVDBShow(self, tvdb_show_id):
    
    """ 
      Retrieve TV Show informations from TVDB API.
       
      Parameters
      ----------
      tvdb_show_id : Int
        TVDB id of the tv show.
        
      Returns
      _______
      tvdb_tvshow_info : Dict {tvdb_show_id : tvdb_tvshow_info}
        A dict that contains the TVDB show informations.
    """
    
    return tvdb_tvshow_info
   
  def getTVDBSeasons(self, tvdb_show_id):
    
    """ 
      Retrieve TV Show seasons list from TVDB API.
       
      Parameters
      ----------
      tvdb_show_id : Int
        TVDB id of the tv show.
        
      Returns
      _______
      tvdb_tvshow_seasons : List [season_number]
        A list that contains the TVDB show seasons.
    """
    
    return tvdb_tvshow_seasons
    
  def getTVDBEpisodes(self, tvdb_show_id, season_number = None):
    
    """ 
      Retrieve TV Show episodes list of a specific season from TVDB API.
       
      Parameters
      ----------
      tvdb_show_id : Int
        TVDB id of the tv show.
      season_number (optionnal) : Int
        Number of the season. [Default = None]
        
      Returns
      _______
      tvdb_tvshows : Dict {tvdb_tvshow_id : tvdb_tvshow_name}
        A dict that contains TVDB shows.
    """
    
    return tvdb_tvshows
    
  # ! Matching methods :
    
  def matchTVShow(self, show_path):
    
    """ 
      Try to match a local TV Show name to TVDB TV Show name.
      Return a list of TVDB TV Shows name, empty if no match, 1 entry if a match is found, multiple entries if multiple match found.
       
      Parameters
      ----------
      show_path : String
        Local TV Show absolute path
        
      Returns
      _______
      tvshows_match : Dict {local_tvshow_name : tvdb_tvshow_list}
        A dict that contains local episode name as key, and list of tvdb match as value.
    """
    
    return tvshow_match
    
  def matchEpisodes(self, show_path, season_number=None):
    
    """ 
      Try to match a local TV Show episodes names to TVDB TV Show episodes names.
      Return a list of TVDB TV Shows episodes names, empty if no match, 1 entry if a match is found, multiple entries if multiple match found.
       
      Parameters
      ----------
      show_path : String
        Local TV Show absolute path.
      season_number (optionnal) : Int
        Number of the season. [Default = None]
      
      Returns
      _______
      episodes_match : Dict {local_episode_name : tvdb_episodes_match_list}
        A dict that contains local episode name as key, and list of tvdb match as value.
    """
    
    return episodes_match

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
        
    # Retrieve local tvshow list.
    self.local_tvshows = self.getLocalTVShows(local_tvshows_path)
    # [DEBUG]
    #print(self.local_tvshows)
    
    # Retrieve TVDB tvshow list.
    self.tvdb_tvshows = self.getTVDBShows(self.local_tvshows)
    # [DEBUG]
    #print(self.tvdb_tvshows)
    
    # Clearing the console.
    self.clearConsole()

    # [DEBUG]
    #print(f"Vous avez choisie : {self.tvdb_tvshows[self.current_local_tvshow_id]}")
    #input("Pressez ENTRER pour continuer...")
    #self.clearConsole()
    
    # IntefacesLevels
    levels = {
      1 : "TVShows",
      2 : "TVShow info",
      3 : "Seasons",
      4 : "Episodes",
    }
    # Current level.
    current_level = 1
    # Current level label.
    current_level_label = levels[current_level]
    
    # Interface loop.
    while True :
    
      # Interface level rewind.
      if self.user_choice == 0 :
        # Check if rewind possible.
        try:
          current_level_label = levels[current_level-1]
          current_level--
        except:
          print(f"Error can't rewind interface level.")
      
      # Switch on interface level : 
      
      # TVShows.
      if current_level == 1 : 
        # Choose TVDB TVShow to process.
        self.current_local_tvshow_id = self.chooseTVShow(self.tvdb_tvshows)
        # Retrieve choosen TVDB TVShow.
        self.current_tvdb_tvshow = self.tvdb_tvshows[self.current_local_tvshow_id]
      # TVShows infos.
      elif current_level == 2 :
        #
        self.user_choice = self.chooseTVDBTVShowInfos(self.current_tvdb_tvshow )
      # Seasons.
      elif current_level == 3 :
        # 
        self.current_season_num =  self.chooseTVShowSeason(self.current_tvdb_tvshow)
      # Episodes.
      elif current_level == 4 :
      
      # Check if increase possible.
      try:
        current_level_label = levels[current_level+1]
        current_level++
      except:
        print(f"Error can't increase interface level.")
          
      # Clearing the console.
      self.clearConsole()
    
      # TVDB TVShow seasons list.
      if self.user_choice == 1 :
        
        # Clearing the console.
        self.clearConsole()
        
        while self.current_season_num is None :
          self.current_season_num =  self.chooseTVShowSeason(self.current_tvdb_tvshow)
        
      # TVDB TVShow season episode list.
      elif self.user_choice == 2 :
        
        # Clearing the console.
        self.clearConsole()
        
        while self.current_episode_num is None :
          self.current_season_num =  self.chooseTVShowSeason(self.current_tvdb_tvshow)
      
      else : # Default.
        
        # Clearing the console.
        self.clearConsole()
        
        # TVDB TVShow list.
        while self.current_local_tvshow_id is None :
          # Choose TVDB TVShow to process.
          self.current_local_tvshow_id = self.chooseTVShow(self.tvdb_tvshows)           
        
        # Retrieve choosen TVDB TVShow.
        self.current_tvdb_tvshow = self.tvdb_tvshows[self.current_local_tvshow_id]
        
        # Clearing the console.
        self.clearConsole()
        
        # TVDB TVShow info. 
        while self.user_choice is None : 
          self.user_choice = self.chooseTVDBTVShowInfos(self.current_tvdb_tvshow )
    
    # [DEBUG]
    input("--- Fin de programme ---")   
        
    # Return
    return None
  
  def checkUserInput(self, possibilities, input_question = "Choisissez une valeur : ", possibility_label = "", force_input = True):
    
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
      force_input : Boolean
        Does the input must be ask until valid. Input is valid if match a possibility in possibilities values and match input_type is not None.
        
      Returns
      _______
      input_index : Int
        Index of the input possibility. 
    """ 
    
    # Input index default value.
    input_index = None
    
    # Formating & prompt.
    print("---------------------------------------------------------------")
    print(f"{input_question}")
    
    # Showing possibilities.
    for possibility_index, possibility_value in possibilities.items() :
      print(f"#{possibility_index} : {possibility_label} {possibility_value}")
      
    # Check user input in possibilities.
    while input_index not in possibilities.keys() :
      
      # Check previous input error.
      if input_index is not None :
        print(f"Index incorrect.")
      
      # Asking for a choice
      input_index = input(f"Entrer l'index : ")
      
      # Check if input is int.
      try:
        input_index = int(input_index.strip())
      except:
        print(f"Saisie incorrect.")
            
        
    # Return input_index.
    return input_index
      
  
  def chooseTVShow(self, tvdb_tvshow_dict):
    
    """ 
      Print TVDB TVShow list for process choice.
       
      Parameters
      ----------
      tvdb_tvshow_dict : Dict
        TVDB TVShow dict {local_tvshow_id : tvdb_tvshow}
        
      Returns
      _______
      local_tvshow_id : Int
        Local TVShow id.
    """
        
    # Create local tvshow ids list to verify user input.
    local_tvshow_ids = []
    
    # Ask user to select a season number.
    local_tvshow_id = self.checkUserInput(tvdb_tvshow_dict, "Choisissez une série à traiter ?")
    
    # Return
    return local_tvshow_id
  
  
  def chooseTVDBTVShowInfos(self, tvdb_tvshow):
    
    """ 
      Print TVDB TVShow information for process choice.
       
      Parameters
      ----------
      tvdb_tvshow : TVDBTVShow
        TVDB TVShow object
        
      Returns
      _______
      user_choice : String
    """
    
    # Retrieving TVDB TVShow infos :
    tvdb_tvshow_id = tvdb_tvshow.data['id']
    #tvdb_tvshow_id2 = tvdb_tvshow.data['seriesId']
    tvdb_tvshow_imdb_id = tvdb_tvshow.data['imdbId']
    tvdb_tvshow_name = tvdb_tvshow.data['seriesName']
    tvdb_tvshow_aliases = tvdb_tvshow.data['aliases']
    tvdb_tvshow_status = tvdb_tvshow.data['status']
    tvdb_tvshow_network = tvdb_tvshow.data['network']
    tvdb_tvshow_season = tvdb_tvshow.data['season']
    tvdb_tvshow_language = tvdb_tvshow.data['language']
    tvdb_tvshow_overview = tvdb_tvshow.data['overview']
    #tvdb_tvshow_last_updated = tvdb_tvshow.data['lastUpdated']
    #tvdb_tvshow_rating = tvdb_tvshow.data['rating']
    tvdb_tvshow_site_rating = tvdb_tvshow.data['siteRating']
    tvdb_tvshow_site_rating_count = tvdb_tvshow.data['siteRatingCount']
    
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
    possibilities[0] = "Retour à la liste des séries."
    
    # Ask user to select a season number.
    possibility_index = self.checkUserInput(possibilities)
    
    # Return
    return possibility_index
    
    
  def chooseTVShowSeason(self, tvdb_tvshow):
    
    """ 
      Print TVDB TVShow season list for process choice.
       
      Parameters
      ----------
      tvdb_tvshow : TVDBTVShow
        TVDB TVShow object
        
      Returns
      _______
      tvshow_season_number : Int
    """
    
    # Choose season to process : 
    
    # Number of seasons.
    tvdb_tvshow_seasons_count = tvdb_tvshow.data["season"]
    
    # [DEBUG]
    #print(f"Number of season : {int(tvdb_tvshow_seasons_count)}")
    
    # Retrieve seasons in dict.
    season_numbers = {}
    season_numbers_id = 1
    season_number_input_id = None
    for season_number in range(1, int(tvdb_tvshow_seasons_count) + 1):
      try:
        # Check if season exist on TVDB.
        tvdb_tvshow[season_numbers_id]
        # Add season to list.
        season_numbers[season_numbers_id] = season_number
      except:
        continue
    
    # Ask user to select a season number.
    season_number_index = self.checkUserInput(season_numbers, "Choisissez une saison à afficher : ", "saison")
    
    # Retrieve season number.
    tvshow_season_number = season_numbers[season_number_index]
    
    # Return.
    return tvshow_season_number
  
  def chooseTVShowEpisodes(self, tvdb_tvshows, tvdb_tvshow_season_number=None):
    
    """ 
      Print TVDB TVShow season list for process choice.
       
      Parameters
      ----------
      tvdb_tvshow : TVDBTVShow
        TVDB TVShow object
      tvdb_tvshow_season_number : Int (optionnal)
        TVDB TVShow season number. [Default = None]
        
      Returns
      _______
      tvshow_episode : Dict [local_tvshow_path : tvdb_tvshow]
    """
    
    # TVDB TVShow name
    print(f"{tvdb_tvshow.data['seriesName']} ")
    # If season selected.
    if tvdb_tvshow_season_number is not None :
      print(f"Season {tvdb_tvshow_season_number} episodes :")
    else:
      print(f"All seasons episodes :")
    print("")
    
    # TVDB TVShow episodes list.
    if tvdb_tvshow_season_number is not None : 
      season = tvdb_tvshows[tvdb_tvshow_season_number]
    else:
      for tvdb_tvshow_season_number in tvdb_tvshow_seasons :
        seasons = tvdb_tvshows[tvdb_tvshow_season_number]
    
    # Ask user to select a episode number.
    episode_number_index = self.checkUserInput(season_numbers, "Choisissez une saison à afficher : ", "saison")
    
    # Retrieve season number.
    tvshow_episode = season_numbers[season_number_index]
    
    # Return
    return tvshow_episode
    
  
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
  
  
  