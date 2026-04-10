#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Import OS
import os
# Import requests
import requests
# Import SQLite v3
import sqlite3
# Import urllib parse.
import urllib.parse
# Import pyvirtualdisplay
from pyvirtualdisplay import Display
# Import selenium
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait 
from selenium.webdriver.support import expected_conditions as EC
# Import webdriver_manager
from webdriver_manager.chrome import ChromeDriverManager
# Import BeautifulSoup
from bs4 import BeautifulSoup
# Import plex API.
from plexapi.server import PlexServer

# Config Web Driver Manager log level.
os.environ['WDM_LOG_LEVEL'] = '0'

# ! Constant vars :

# Interactive mode, ask for each item if update needed.
INTERACTIVE = False
# Update only item without current value.
UPDATE_ONLY = True
# Update types
UPDATE_TYPES = {
  1 : "Films",
  2 : "Séries",
}
# Update type.
UPDATE_TYPE = UPDATE_TYPES[1]
# Max search retry.
SEARCH_MAX_RETRY = 2
# Max update retry.
UPDATE_MAX_RETRY = 2
# Add this value to SC rating.
RATING_INCREASE = 0
# Minimum value admit for rating.
RATING_MIN_VALUE = 0
# Maximal value admit for rating.
RATING_MAX_VALUE = 10
# SensCritique base url. (should end with /)
SC_BASE_URL = "https://www.senscritique.com/"
# SensCritique item type filter for search.
if UPDATE_TYPE == "Films" :
  SC_MEDIA_FILTER = "Films"
if UPDATE_TYPE == "Séries" :
  SC_MEDIA_FILTER = "Séries"
# Plex server URL.
PLEX_SERVER_URL = "http://192.168.0.110:32400"
# Plex SQLite file path.
PLEX_SQLITE_FILEPATH = "/Volumes/Users/izno/AppData/Local/Plex Media Server/Plug-in Support/Databases/com.plexapp.plugins.library.db"
# Plex server Tokens.
PLEX_SERVER_TOKENS = {
  "izno" : "FykyWGwsoLWrxozHL2b_",
  "laura" : "yUzyx9htpcSMAxUjEzm2",
  "salon" : "FykyWGwsoLWrxozHL2b_",
}
# Plex server Token.
PLEX_SERVER_TOKEN = PLEX_SERVER_TOKENS["izno"]
# Plex server library section name.
if UPDATE_TYPE == "Films" :
  PLEX_LIBRARY_SECTION = "Films"
if UPDATE_TYPE == "Séries" :
  PLEX_LIBRARY_SECTION = "Séries TV"
# Collection filter.
COLLECTION_FILTER = "Théatre" # None

# Class.
class PlexSensCritique:
  
  """ PlexSensCritique class. """
  
  def __init__(self):
    
    """ PlexSensCritique class constructor. """
    
    # Try to create a invisible virtual display for browser.
    self.display = None
    self.__getVirtualDisplay()
   
    # Create a fake browser to execute JS with selenium.
    self.browser = None
    self.__getVirtualBrowser()
    
    # Create a Plex Server instance to access Plex API.
    self.plex_server = None
    self.__getPlexServerConnexion()
    
    # Create a Plex Server Database connexion.
    self.plex_sql = None
    self.__getPlexSQLConnexion()
      
  def __del__(self):
    
    """ PlexSensCritique class destructor. """
    
    # Close browser if exist.
    try:
      self.browser.quit()
      pass
    except:
      pass
      
    # Stop invisible virtual display if exist.
    try:
      self.display.stop()
      pass
    except:
      pass
  
  def __getVirtualDisplay(self):
    
    """
      __getVirtualDisplay : Create a invisible virtual display for browser.
    """
    
    # Close previous virtual display if exist.
    if self.display : 
      self.display.stop()
    
    # Try to create a invisible virtual display for browser.
    try:
      # Create a virtual invisible display for the futur browser instance.
      self.display = Display(visible=0, size=(800, 600))
      # Start invisible virtual display.
      self.display.start()
    except Exception as exception:
      # DEBUG
      #print("Unable to create invisible virtual display.") 
      #print(f"{exception}")
      #print(f"Continue in visual display mode.")
      pass
    
  def __getVirtualBrowser(self):
    
    """
      __getVirtualBrowser : Create a fake browser to execute JS with selenium.
    """
    
    # Close previous virtual browser if exist.
    if self.browser :
      self.browser.quit()
    
    # Create a fake browser to execute JS with selenium.
    try:
      self.browser = webdriver.Chrome(service=Service(ChromeDriverManager().install()))
    except Exception as exception:
      # DEBUG
      print("Unable to create virtual browser for search.") 
      #print(f"{exception}")
    
  def __getPlexServerConnexion(self):
    
    """
      __getPlexServerConnexion : Create a Plex Server instance to access Plex API.
    """
    
    if self.plex_server :
      self.plex_server = None
    
    # Create a Plex Server instance to access Plex API.
    try:
      self.plex_server = PlexServer(PLEX_SERVER_URL, PLEX_SERVER_TOKEN)
    except Exception as exception:
      # DEBUG
      print("Unable to create plex server API connexion.") 
      #print(f"{exception}")
      
  def __getPlexSQLConnexion(self):
    
    """
      __getPlexSQLConnexion : Create a Plex Server database connexion.
    """
    
    if self.plex_sql :
      self.plex_sql = None
    
    # Create a Plex Server instance to access Plex API.
    try:
      self.plex_sql = sqlite3.connect(PLEX_SQLITE_FILEPATH)
    except Exception as exception:
      # DEBUG
      print("Unable to create plex SQL connexion.") 
      #print(f"{exception}")
    
    
  def getPlexLibrarySectionItems(self, section_name):
    
    """
      getPlexLibrarySectionItems : Retrieve plex library section items by library section name.
      ---
      Parameters : 
        section_name : String
          Plex library section name.
      ---
      Return : List
        Plex API library section items list.
    """
    
      
    # Retrieve a library section by name. (This is the name you give when you create the library section.)
    plex_library_section = self.plex_server.library.section(section_name)
    
    # Get all items from this section, with filter if defined.
    if COLLECTION_FILTER is None :
      plex_library_section_items = plex_library_section.all()
    else:
      plex_library_section_items = plex_library_section.search(collection=COLLECTION_FILTER)
    
    # Return items list.
    return plex_library_section_items
  
  
  def updatePlexLibrarySectionItemRating(self, section_name, item, new_rating):
    
    """
      updatePlexLibrarySectionItemRating : Update item rating via Plex Server API.
      ---
      Parameters : 
        section_name : String
          Name of the library section the item is located in.
        item : Plex Item Object
          Plex item to update.
        new_rating : Float
          New rating value.
      ---
      Return : Boolean
        Item update successfully.
    """
    
    # Control new rating is float compatible and add increase value.
    try:
      new_rating = float(new_rating) 
      if RATING_INCREASE :
        new_rating = new_rating + RATING_INCREASE
    except:
      # DEBUG
      print("Can't parse new rating value to float.")
      # Return.
      return False
      
    # Check rating min value.
    if new_rating < RATING_MIN_VALUE :
      new_rating = RATING_MIN_VALUE
      
    # Check rating max value. 
    if new_rating > RATING_MAX_VALUE :
      new_rating = RATING_MAX_VALUE
    
    # DEBUG
    print(f"Updating rating from {item.userRating} to {new_rating}")
    
    # If update is needed.
    if item.userRating != new_rating :
      # Update library section item via Plex server API.
      try:
        item.rate(new_rating)
      except:
        self.__getPlexServerConnexion()
    
    # Return.
    return True
  
  def getSCResults(self, search_query, search_with_filter = True):
    
    """
      getSCResults : Create a virtual Chrome Browser (in a invisible virtual display if available on OS) 
      and make a SensCritique search via the default search URL.
      ---
      Parameters :
        search_query : String
          Query string to search on SensCritique, string is URL encoded.
        search_with_filter : Boolean
          Define if we add filter on SC search.
      ---
      Return : List of BeautifulSoupTag Object.
        BS Tag Object list that contain all the results.
    """
    
    # List of BS Tag object.
    sc_html_search_result_cards = []
    
    # ! EXCEPTIONS :
    search_query = search_query.replace(".", " ")
    search_query = search_query.replace("·", " ")
    search_query = search_query.replace("º", "º ")
    
    # URL encode space char.
    url_encoded_search_query = urllib.parse.quote(search_query)
    
    # SensCritique search default URL. 
    if search_with_filter and COLLECTION_FILTER is None : 
      sc_search_url = f"{SC_BASE_URL}search?filters%5B0%5D%5Bidentifier%5D=universe&filters%5B0%5D%5Bvalue%5D={SC_MEDIA_FILTER}&query={url_encoded_search_query}"
    else:
      sc_search_url = f"{SC_BASE_URL}search?query={url_encoded_search_query}"
    
    
    # SensCrituqe result page HTML source code.
    sc_html_search_result_page = None
    
    # Try to get SensCritique page via virtual browser.
    try:
      # Retrieve the search result page from SensCritique.
      self.browser.get(sc_search_url)
      # Waiting for particular div class_name to appear on page.
      element = WebDriverWait(self.browser, 10).until(
        # EC check the presence of results cards.
        EC.presence_of_element_located((By.CLASS_NAME, "Rating__GlobalRating-sc-1rkvzid-4"))
      )
      # Get SensCrituqe result page HTML source code.
      sc_html_search_result_page = self.browser.page_source
    except Exception as exception:
      # DEBUG
      print("Unable to get HTML page via virtual browser.") 
      print(f"URL : {sc_search_url}")
      #print(f"{exception}")
      # Try to create new browser session.
      self.__getVirtualBrowser()
    
    # If get HTML page successful.
    if sc_html_search_result_page : 
      # Try to retrieve data on page.
      try:  
        # Create a BeautifulSoup Object with the HTML page.
        page_soup = BeautifulSoup(sc_html_search_result_page, 'html.parser')
        # Retrieve the search result div from SensCritique.
        sc_html_search_result_cards = page_soup.find_all("div", {"class": "ExplorerProductCard__Container-sc-1fw1q8r-0"}) 
      except Exception as exception:
        # DEBUG
        print("Unable to parse SensCritique page.")
        print(f"URL : {sc_search_url}")
    
    # Return the list of BS tag results.
    return sc_html_search_result_cards
  
  
  def getSCResult(self, search_query, result_number = 1, search_with_filter = True):
    
    """
      getSCResult : Call getSCResults and retrieve result_number position result BS Tag.
      ---
      Parameters :
        search_query : String
          Query string to search on SensCritique.
        result_number : Int
          Position of the result to retrieve in results list.
        search_with_filter : Boolean
          Define if we add filter on SC search.
      ---
      Return : BeautifulSoupTag Object / None.
        BS Tag Object that contain the first result, None if not found.
    """
    
    # Result to return default value.
    bs_result = None
    
    # Get SensCritique search first result from
    bs_results = self.getSCResults(search_query, search_with_filter)
    
    # Retrieve the result at result_number position.
    try:
      bs_result = bs_results[result_number - 1]
    except:
      pass
    
    # Return 
    return bs_result
  
  def getSCResultDict(self, search_query, result_number = 1, search_with_filter = True, getMoreInfos = False):
    
    """
      getSCResultDict : Call getSCResult and retrieve result then convert it in dict.
      ---
      Parameters :
        search_query : String
          Query string to search on SensCritique.
        result_number : Int
          Position of the result to retrieve in results list.
        search_with_filter : Boolean
          Define if we add filter on SC search.
        getMoreInfos : Boolean
          Retrieve additional infos from media specific page.
      ---
      Return : Dict.
        Result as dict.
    """
    
    # Create result dict from result BS Tag Object.
    result = {
      "title" : "",
      "rating" : "",
      "year" : "",
      "genres" : [],
    }
  
    # Get SensCritique search first result from
    bs_result = self.getSCResult(search_query, result_number, search_with_filter)
    
    # Check if result found.
    if bs_result : 
      
      # Result infos dict.
      #result["raw"] = bs_result
      #result["str"] = bs_result.text


      # Retrieve infos from BeautifulSoup tag Object.
      result["link"] = SC_BASE_URL + bs_result.find("a", {"class" : "Text__SCText-sc-14ie3lm-0"})["href"]
      result["SCID"] = result["link"].split('/')[-1]
      result["poster"] = bs_result.find("img")["src"].replace("data:image/svg+xml,%3csvg%20xmlns=%27", "")
      result["title"] = bs_result.find("h3").text
      
      try:
        result["rating"] = bs_result.find("div", {"class" : "Rating__GlobalRating-sc-1rkvzid-4"}).text
      except:
        pass
      
      author_year_list = bs_result.find_all("p", {"class" : "Text__SCText-sc-14ie3lm-0"})[0].text.split("·")
      result["author"] = author_year_list[0].replace("Film de ", "")
      
      try:
        result["year"] = author_year_list[1]
      except:
        pass
        
      try:
        result["genres"] = infos[1].text.split(',')
      except:
       pass

      
      # If additionnal infos requested.
      if getMoreInfos is True :
      
        # Retrieve HTML of media specific page.
        html_response = requests.get(link).content
    
        # Parse HTML page with BeautifulSoup.
        media_page_soup = BeautifulSoup(html_response, 'html.parser')
        
        # Retrieve additionnal infos.
        resume = media_page_soup.find("p", {"class" : "ProductSynopsis__Text-sc-v8f9yy-0"}).text
        
        # Add additional infos to result dict.
        result["resume"] = resume
    
    
    # Return result dict.
    return result


#####################################################################################################   
#                                            MAIN                                                   #
#####################################################################################################   

# Execute if run as script. 
if __name__ == "__main__":

  # Create instance of PlexSensCritique.
  psc = PlexSensCritique()
  
  # Get Plex movies library section items.
  plex_items = psc.getPlexLibrarySectionItems(PLEX_LIBRARY_SECTION)
      
  # Iterate through movies.
  for plex_item in plex_items :
        
    # Update success.
    item_search_success = False
    
    # Search error count.
    item_search_error_count = 0
    
    # Update success.
    item_update_success = False
    
    # Update error count.
    item_update_error_count = 0
  
    # Get title from movie item.
    plex_movie_title = plex_item.title
    
    # Update rating only if current rating is None.
    if plex_item.userRating is None or UPDATE_ONLY is False :   
    
      # DEBUG
      print(f"{plex_movie_title} ? ")   
      
      # Try to search n times while not succeed.
      while item_search_success is False and item_search_error_count < SEARCH_MAX_RETRY : 
        
        # Remove search filter if search error.
        if item_search_error_count > 0 :
          search_filter = False
        else:
          search_filter = True
        
        # Search for the movie on SensCritique.
        movie_result = psc.getSCResultDict(plex_movie_title, 1, search_filter)
        
        # Check movie result SCID to know if item found.
        if 'SCID' in movie_result.keys():
          # Search success.
          item_search_success = True
          # DEBUG
          print(f"{movie_result['title']} [{movie_result['SCID']}] : {movie_result['rating']}")
        else:
          # Increase search error count.
          item_search_error_count = item_search_error_count + 1
            
      # If we have SensCritique rating.
      if movie_result['rating'] :
      
        # Ask if should update rating for this item.
        user_input = None
        
        # If interactive mode.
        if INTERACTIVE :
          while user_input is None :
            print(f"Mettre à jour la note ?")
            print(f" #1 = Oui ")
            print(f" Autre touche pour continuer... ")
            user_input = str(input(f"? => "))
          
            # Check user input.
            if user_input not in ['1', '2'] :
              # Reset user_input var.
              user_input = None
            
        # If user response is yes or not interactive mode.
        if user_input == '1' or INTERACTIVE is False :
          # Try to update n times while not succeed.
          while item_update_success is False and item_update_error_count < UPDATE_MAX_RETRY : 
            # Update plex item rating.
            item_update_success = psc.updatePlexLibrarySectionItemRating(PLEX_LIBRARY_SECTION, plex_item, movie_result['rating'])
            # Check if update successful.
            if not item_update_success :
              # Increase update error count.
              item_update_error_count = item_update_error_count + 1
              # DEBUG 
              print(f"Update error.")
          
      else:
        # DEBUG
        print(f"No SensCritique rating available.")
    
      # DEBUG
      print(f"----------------------------------------------------------------------------")
  
    
#   # Search query.
#   search_query = "Alex Lutz Sur Scene Formule Enrichie"
#   
#   # Get SensCritique search first result from
#   result = psc.getSCResultDict(search_query, 1, True)
#   
#   # DEBUG
#   print(f"Result : \n {result}")

