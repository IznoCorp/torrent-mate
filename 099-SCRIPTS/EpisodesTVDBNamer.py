# ! Imports :

# Import module os  
from os import listdir, mkdir, rename
from os.path import isfile, isdir, join, basename, splitext
from requests import get
from bs4 import BeautifulSoup
from unidecode import unidecode
from termcolor import colored
import colorama

# ! Variables globales :
  
# DryRun (Change by question)
dryrun = True

# Show Missing only
missing_only = True

# TVBD TV Show name.
tvshow_name = "steven-universe"

# TVBD Show URL.
tvdb_show_base_url = f"https://thetvdb.com/series/{tvshow_name}/seasons/official/"

# Nombre de chiffre au numéro de saison
nb_digit_season = 2

# Debug check un numéro de saison particulier.
debug_season_num = '' # Laissez vide pour désactiver.

# Chemin vers les disques.
medias_path = "N:/a trier/004 SERIES ANIMATIONS/Steven Universe/"
done_media_path = medias_path+"TVDBNamer/"

# Numéro de début et fin de saison.
season_start = 1
season_end = 2

# Retrait de caractères en amont et en aval du nom de fichier. 
# (0 si pas de trim à gauche, right_trim est négatif, None si pas de trim à droite)
left_trim = 7
right_trim = None

# Récupération de la liste des dossiers de saison.
seasons = [folder for folder in listdir(medias_path) if isdir(medias_path+folder)]

# Tableau de récupération de tout les épisodes.
all_tvdb_num_to_name = {}
all_matches = {}
all_missing_matches = {}

# ! Initialisation :

# Initialisation des couleurs du terminal pour Windows.
colorama.init()

# ! Fonctions de tokenization :

# Création d'une fonction de nettoyage du nom.
def basenameToCleanName(episode_basename):
  # Récupération du nom d'épisode depuis le nom de fichier.
  episode_file_name = splitext(episode_basename)[0][left_trim:right_trim].strip()
  # Nettoyage du nom d'épisode.
  episode_clean_name = cleanName(episode_file_name)
  return episode_clean_name
  
# Création d'une fonction de nettoyage du nom.
def cleanName(name):
  # Nettoyage générique : 
  
  # Suppression des accents.
  name = unidecode(name)
  
  # Mise en minuscule.
  name = name.lower()
  
  # Liste des remplacements :
  name = name.replace("&", "and")
  name = name.replace(" et ", " ")
  name = name.replace(".", "")
  name = name.replace("(", "")
  name = name.replace(")", "")
  name = name.replace(",", "")
  name = name.replace("?", "")
  name = name.replace("!", "")
  name = name.replace(" the ", " ")
  name = name.replace("ñ", "n")
  name = name.replace(" deux ", " 2 ")
  
  # Retrait des doubles espaces.
  name = " ".join(name.split())
  
  return name

# Création d'une fonction de tokenisation.
def tokenizeEpisodeName(name):
  
  # Nettoyage du nom.
  name = cleanName(name)
  
  # Valeurs de sortie de tokens
  tokens = []
  
  # Token 0
  token0 = name
  tokens.append(token0)
  
  # ! - Remplacements :
  
  # Token liste des remplacements
  remplacement_strings = {
    "(1/2)" : "1/2",
    "(1 sur 2)" : "1/2",
    "1 sur 2" : "1/2",
    "(1sur2)" : "1/2",
    "1sur2" : "1/2",
    "(2/2)" : "2/2",
    "(2 sur 2)" : "2/2",
    "2 sur 2" : "2/2",
    "(2sur2)" : "2/2",
    "2sur2" : "2/2",
    "(1/3)" : "1/3",
    "(1 sur 3)" : "1/3",
    "1 sur 3" : "1/3",
    "(1sur3)" : "1/3",
    "1sur3" : "1/3",
    "(2/3)" : "2/3",
    "(2 sur 3)" : "2/3",
    "2 sur 3" : "2/3",
    "(2sur3)" : "2/3",
    "2sur3" : "2/3",
    "(3/3)" : "3/3",
    "(3 sur 3)" : "3/3",
    "3 sur 3" : "3/3",
    "(3sur3)" : "3/3",
    "3sur3" : "3/3",
    "(1/4)" : "1/4",
    "(1 sur 4)" : "1/4",
    "1 sur 4" : "1/4",
    "(1sur4)" : "1/4",
    "1sur4" : "1/4",
    "(2/4)" : "2/4",
    "(2 sur 4)" : "2/4",
    "2 sur 4" : "2/4",
    "(2sur4)" : "2/4",
    "2sur4" : "2/4",
    "(3/4)" : "3/4",
    "(3 sur 4)" : "3/4",
    "3 sur 4" : "3/4",
    "(3sur4)" : "3/4",
    "3sur4" : "3/4",
    "(4/4)" : "4/4",
    "(4 sur 4)" : "4/4",
    "4 sur 4" : "4/4",
    "(4sur4)" : "4/4",
    "4sur4" : "4/4",
    "xxieme" : "21eme",
    " ½" : "½", 
    "½" : "",
    "bir-r-r-d" : "bir-r-rd",
    "operation" : "operation:",
    "z-z-z-z" : "zzzz",
    "'s" : "s", 
    "rocket" : "rock", 
    "cop21" : "cop 21", 
  }
  
  # Création des tokens.
  replacement_token = name
  for old_string, new_string in remplacement_strings.items() :
    # Création du token de remplacement.
    replacement_token = replacement_token.replace(old_string, new_string)
  # Retrait des doubles espaces.
  replacement_token = " ".join(replacement_token.split())
  # Ajout du token à la liste.
  tokens.append(replacement_token)
  
  # ! - Retraits : 
  
  # Liste des elements à retirer.
  removed_strings = ["-", " -", "/", " :", ": ", " un ", " une ", "l'", " le ", " la ", " les ", "'", " de ", " des ", "c'", "d'", "n'", "s'", "y'", "<<", ">>"]
  
  # Création des tokens.
  removed_token = replacement_token
  for removed_string in removed_strings :
    # Création du token de remplacement.
    removed_token = removed_token.replace(removed_string, " ")
  # Retrait des doubles espaces.
  removed_token = " ".join(removed_token.split())
  # Ajout du token à la liste.
  tokens.append(removed_token)
  
  # Suppression des doublons
  tokens = list(set(tokens))
  
  # Retourne la liste de tokens.
  return tokens
  




# ! Boucle saisons

# Parcours la liste des saisons.
for season in range(season_start, season_end+1):
  
  # Saisie utilisateur.
  inputKey = 'r'
  
  # Boucle terminale.
  while inputKey in ['r', 'R'] :
    
    # [DEBUG]
    #print(f"Traitement saison {season}")
    
    # ! Variables saison :
    
    # Transforme season en chaine de caractère.
    season = str(season)
    # Add 0 before season number if season on 1 digit.
    if len(season) == 1:
      season = f"0{season}"
    # Flag for missing matches.
    missing_matches_flag = False
    # Tableau de matches.
    matches = {}
    # Tableau de missing matches.
    missing_matches = {}
    # Déclaration d'un tableau de correspondance par saison numEpisode => nameEpisode.
    tvdb_num_to_name = {}
    # Récupération du numéro de la saison.
    season_num = season[-nb_digit_season:]
    
    # Chemin du dossier de la saison.
    season_path = f"{medias_path}Saison {season}/"
    
    # [DEBUG]
    if debug_season_num != '' :
      if season_num != debug_season_num :
        # Passe au prochain tour de boucle sans éxécuté le reste du code pour ce tour de boucle.
        inputKey = None
        continue  
    
    # ! Scrapping TVDB
    
    # Création de l'URL TVDB.
    tvdb_show_season_url = tvdb_show_base_url+season_num
    # Récupération du contenu de la page TVDB pour la saison.
    html_content = get(tvdb_show_season_url, 'html.parser')
    # Utilisation de BeautifulSoup pour parsé le HTML. (Création d'un Objet)
    html_soup = BeautifulSoup(html_content.text, 'html.parser')
    
    # Si j'ai un tbody pour la page (sinon surement une 404 = saison n'existe pas).
    if html_soup.table is not None :
      # Récupération de tout les tr de la 1ère table de données.
      for tr in html_soup.table.tbody.find_all('tr') :
        # Pour chaque tr on récupère les td.
        td_list = tr.find_all('td')
        # Récupération du numéro d'épisode.
        season_num_episode = td_list[0].string
        num_episode = season_num_episode[-2:]
        # Récupération du nom de l'épisode.
        name_episode = td_list[1].find('a').string.strip()
        # Nettoyage du nom d'épisode.
        name_episode = cleanName(name_episode)
        # Tokenisation des noms d'épisode TVDB.
        tokens_name_episode = tokenizeEpisodeName(name_episode)
        # Enregistrement dans le tableau numToName des épisodes.
        tvdb_num_to_name[(season_num, num_episode)] = tokens_name_episode
      
      # Ajout des episodes de la saison au tableau globale.
      all_tvdb_num_to_name.update(tvdb_num_to_name)
    
    # ! Match des épisodes par saison :
    
    # Traitement des fichiers du dossier de saison, seulement si il existe.
    if isdir(season_path) :
          
      # Récupérer les noms d'épisodes dans les fichiers du dossier de saison.
      episodes_basenames = [episode_basename for episode_basename in listdir(season_path) if isfile(season_path+episode_basename)]
      
      # Pour chaque épisodes du dossier de saison.
      for episode_basename in episodes_basenames:
        # Flag for match.
        match = False
              
        # Nettoyage du nom d'épisode.
        episode_clean_name = basenameToCleanName(episode_basename)
        folderTokensNames = tokenizeEpisodeName(episode_clean_name)
        
        # [DEBUG]
        #print("----------------------------------------------------------------------")
        #print("----------------------------------------------------------------------")
      
        # Vérification si on le trouve dans la liste des épisodes de TVDB pour la saison.
        for keyEpisode, TVDBTokensNames in tvdb_num_to_name.items():         
            
          # Récupération du numéro d'épisode.
          numEpisode = keyEpisode[1]
                
          # Test de match.
          for TVDBtokenName in TVDBTokensNames :
            # [DEBUG]
            #print("-----------------------------------")
            #print(TVDBTokensNames)
            #print(folderTokensNames)
            # Si match.
            if TVDBtokenName in folderTokensNames :
              match = True
              matches[(season_num, numEpisode)] = episode_basename
              break
        # Si no match.
        if not match :
          missing_matches_flag = True
          missing_matches[episode_basename] = season_num
    else:
        print(f"Le dossier {season_path} n'existe pas")
    
    # Ajout des matches aux matches globales
    all_matches.update(matches)
    # Ajout des missings matches aux missings matches globales
    all_missing_matches.update(missing_matches)
    
    # ! Affichage resultats match saison :
    
    # Affichage matching
    if not missing_only :
      for keyEpisode, nameEpisode in matches.items() :
        numSeason = keyEpisode[0]
        numEpisode = keyEpisode[1]
        # [DEBUG]
        print(colored(f"Match found for {nameEpisode} => #{numEpisode}", 'green'))
    
    # Affichage missing
    if missing_matches_flag :
      # URL TVDB
      print(f"TVDB URL : {tvdb_show_season_url}")
      # Liste des episodes TVDB
      for keyEpisode, TVDBTokensNames in tvdb_num_to_name.items():
        # [DEBUG]
        print(TVDBTokensNames)
      # Liste des épisodes de dossiers n'ayant pas matché.
      for episode_basename, seasonNum in missing_matches.items() :
        # Nettoyage du nom d'épisode.
        episode_clean_name = basenameToCleanName(episode_basename)
        # [DEBUG]
        print(colored(tokenizeEpisodeName(episode_clean_name), 'yellow'))
        print(colored(f"No match found for {episode_clean_name}", 'red'))
      # [DEBUG] Pause.
      inputKey = input("Press any key to go next. 'R' to reload.")
    else:
      # Passe au prochain tour de boucle.
      inputKey = None
      continue
  
# ! Traitement globaux (toutes saisons) : 

# ! - Traitement des missing matches :

# Pour chaque missing match.
for episode_basename, missing_match_season in all_missing_matches.items() : 
  # Nettoyage du nom d'épisode.
  episode_clean_name = basenameToCleanName(episode_basename)
  # Tokenization du nom d'épisode du dossier.
  folderTokensNames = tokenizeEpisodeName(episode_clean_name) 
  # On parcours tout les épisodes TVDB.
  for keyEpisode, TVDBTokensNames in all_tvdb_num_to_name.items() :
    numSeason = keyEpisode[0]
    numEpisode  = keyEpisode[1]
    # Test de match pour chaque token TVDB.
    for TVDBtokenName in TVDBTokensNames :
      # On vérifie si le token TVDB match un des token du nom d'épisode de dossier.
      if TVDBtokenName in folderTokensNames :
        # [DEBUG]
        print(colored(f"Missing match retrouvé : Saison {missing_match_season}/{episode_basename} => S{numSeason}E{numEpisode} {episode_clean_name}", 'cyan'))
        # Ajout du missing match aux matches.
        all_matches[(numSeason, numEpisode, missing_match_season)] = episode_basename
        break
      
# ! - Traitement des match :

# Création du dossier de traitement.
if not isdir(done_media_path):
  # Création du dossier
  mkdir(done_media_path)

# Choose if dryrun or not.
inputKey = input("Press any key to dry run. 'Yes' to move and rename files.")
if inputKey in ['y', 'Y', 'yes', 'Yes', 'YES'] :
  # Stop the Dry Run.
  dryrun = False
  # Debug for dryrun
  print(f" --- DRY RUN FALSE. Renamming... --- ")
else:
  # Active the Dry Run. (debug mode no modification)
  dryrun = True
  # Debug for dryrun
  print(f" --- DRY RUN TRUE. Show debug only... --- ")

# Reset inputKey
inputKey = None

# Pour chaque episode matché.
for keyEpisode, episode_basename in all_matches.items() :
  numSeason = keyEpisode[0]
  numEpisode = keyEpisode[1]
  try:
    oldNumSeason = keyEpisode[2]
  except:
    oldNumSeason = None
  
  nameEpisode = splitext(episode_basename)[0][left_trim:right_trim].strip()
  fileExtension = splitext(episode_basename)[1]
  # On récupère le chemin de départ.
  if oldNumSeason :
    old_episode_path = f"{medias_path}Saison {oldNumSeason}/{episode_basename}"
  else:
    old_episode_path = f"{medias_path}Saison {numSeason}/{episode_basename}"
  # On crée le chemin d'arrivé.
  new_episode_path = f"{done_media_path}Saison {numSeason}/S{numSeason}E{numEpisode} - {nameEpisode}{fileExtension}"
  # On verifie que le dossier existe.
  # Création du dossier de traitement.
  if not isdir(f"{done_media_path}Saison {numSeason}"):
    # Création du dossier
    mkdir(f"{done_media_path}Saison {numSeason}")
  # Traitement, si non dry run.
  if dryrun :
    # Debug for dryrun
    print(f" --- rename ---")
    print(f"{old_episode_path}")
    print(f"{new_episode_path}")
  else:
   # Debug for dryrun
    print(colored(f" --- rename ---", 'green'))
    print(f"{old_episode_path}")
    print(f"{new_episode_path}")
    # On déplace et renomme le fichier.
    rename(old_episode_path, new_episode_path)
    

# Evite la fermeture de la fenêtre à la fin de l'exécution.
input("Press enter to exit ;)")