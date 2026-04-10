# ! Imports :

# Imports from module os and os.path
from os import listdir, mkdir, rename, walk, rmdir
from os.path import isfile, isdir, join, basename, splitext, dirname, abspath
from re import split

# Defines all paths.
ROOT_PATH = f"N:/a trier/"
PACK_PATH = f"{ROOT_PATH}0001/"
MOVIES_PATH = f"{ROOT_PATH}001 FILMS/"

# Dry run.
DRY_RUN = False

# Unpack method.
def clean_name(name):
  
  """
    clean_name : Clean a file or folder name.
    ---
    Parameters 
      name : String
        Name to clean.
    --- 
    Return : String
      Name cleaned.
  """
  
  # Récupération de l'extension
  root, extension = splitext(name)
  
  # Passer le nom en minuscules
  root = root.lower()
  
  # Ajout d'un espace en fin de nom de fichier pour faciliter le match des mots à retirer
  root = root + " "
  
  # Remplacement de caractères dans le nom du fichier 
  chars_to_delete = [
    "5.1", 
    "4.0", 
    ".", 
    "web-dl",
    "-", 
    "_", 
    "[", 
    "]", 
    " french ", 
    "truefrench", 
    " vff ", 
    " multi ", 
    "vf2", 
    " x264 ", 
    " x265 ", 
    "10bit", 
    " he ", 
    " aac ", 
    " acc ",
    " ark01 ",
    " web ",
    "jiheff",
    " mkv ",
    " lcds ",
    " qtz ",
    " hevc ",
    " hdma ",
    " extreme ",
    " extended ",
    " 1920x1080 ",
    " vmpp ",
    " 4klight ",
    " dolby vision ",
    " unrated ",
    " uptopol ",
    " hdtv ",
    " shc23 ",
    " aaclc ",
    " notag ",
    " bdrip ",
    " hdr ",
    " kfl ",
    " dts ", 
    " integrale ", 
    " integral ", 
    " internal ", 
    " 720p ", 
    " 1080p ", 
    "hdlight", 
    " fr ", 
    " fre ", 
    " en ", 
    " eng ", 
    " vfq ", 
    "mhdgz", 
    "ac3", 
    "dvdrip", 
    "brrip", 
    "xvid", 
    "bluray", 
    "pophd", 
    "tvwh0res",
    "gismo65", 
    "trunkdu92",  
    "frosties", 
    "h265",
    "h264",
    "abcollection",
    "vmpp",
    " owii ",
    " ght ", 
    " ghz ", 
    " noex ", 
    "(fasandraeberne)", 
    " luminus ", 
    "(kvinden i buret)", 
    "(flaskepost fra p)"
  ]
  for char in chars_to_delete: 
    root = root.replace(char, " ")
    
  # Suppression des espaces mutiples 
  root = " ".join(split(r"\s+", root))

  # Suppression des espaces en début et en fin de phrase
  root = root.strip()

  # Création d'une variable name_cleaned contenant name 
  name_cleaned = root + extension
  
  # Récupération de la variable name_cleaned 
  return name_cleaned
  


# Unpack method.
def unpack(main_folder_path, treat_files = False):
  
  """
    Prendre les fichiers pour chaque sous-dossier de main_folder_path et les déplacer dans main_folder_path 
    ---
    Parameters
      main_folder_path : String
        Dossier principal dans lequel l'ensemble des fichiers sera déplacé.
      treat_files : Boolean
        Définie si les fichiers de main_folder_path sont à traiter. (CàD. Remonter d'un niveau)
  """
  
  # Affichage debug 
  print(f"Unpack : {main_folder_path}")
  
  # Récupération du chemin de dossier parent de main_folder_path 
  main_folder_path_parent = abspath(join(main_folder_path, "..")) + "/"
  
  # Parcours des dossiers et fichiers présents dans le dossier et création d'une liste des dossiers et une liste des fichiers 
  for path, dirs, files in walk(main_folder_path):
    
    # Affichage debug 
    print(f"Traitement du dossier : {main_folder_path} => {isdir(main_folder_path)}")
    
    # Pour chaque dossier dans l'ensemble des sous-dossiers de niveau 1 présents dans le dossier principal  
    for dir_name in dirs: 
      
      # Chemin complet du sous-dossier.
      sub_folder_path =  main_folder_path + dir_name + "/"
      
      # Affichage debug 
      print(f"Sous-dossier : {sub_folder_path} => {isdir(sub_folder_path)}")
      
      # Prendre les fichiers pour chaque sous-dossier de dirname_path et les déplacer dans dirname_path
      unpack(sub_folder_path, True) 

    # Création d'un listing des noms de fichiers présents dans le dossier 
    for filename in files:
  
      # Nettoyage du nom de fichier d'arrivé.
      filename_cleaned = clean_name(filename)
      
      # Chemin de fichier de départ.
      old_file_path = main_folder_path + filename
      # Chemin de fichier d'arrivée.
      new_file_path = main_folder_path + filename_cleaned
      
      # Affichage debug 
      print("------------------------------------------------")
      print(f"{old_file_path} => {isfile(old_file_path)} ")

      # Traitement des fichiers quand treat_files est vrai  
      if treat_files is True and DRY_RUN is False: 
        # Déplacement de fichier du dossier vers son dossier parent et nettoyage du nom de fichier.
        rename(main_folder_path + filename, main_folder_path_parent + filename_cleaned)
      else:
        # Nettoyage du nom de fichier sans déplacer le fichier dans le parent.
        rename(main_folder_path + filename, main_folder_path + filename_cleaned)
      
      # Affichage debug 
      print("")
      print(f"{new_file_path} => {isfile(new_file_path)}")
      print("------------------------------------------------")
     
  # Si le déplacement des fichiers vers le parents à eu lieu.
  if treat_files is True and DRY_RUN is False: 
    # Suppression du dossier vidé.
    rmdir(main_folder_path)

# Pack method.
def pack(main_folder_path):
  
  """
    pack : List all files in main folder and create a corresponding named folder, then put the file in the corresponding folder.
    ---
    Parameters
      main_folder_path : String
        Path of the root folder to parse.
  """
  
  # Parcours des dossiers et fichiers présents dans le dossier et création d'une liste des dossiers et une liste des fichiers.
  for path, dirs, files in walk(main_folder_path):
    # Pour chaque fichiers dans le dossier main_folder_path.
    for filename in files:
      # Récupération du nom de fichier sans extension.
      root, extension = splitext(filename)
      # Création du chemin de dossier.
      file_folder_path = main_folder_path + root + '/'
      # Affichage debug.
      print(f"Pack : {filename}")
      # Création d'un dossier nommé comme le nom de fichier.
      if DRY_RUN is False :
        mkdir(file_folder_path)
        # Déplacement du fichier vers le nouveau dossier créer.
        rename(main_folder_path + filename, file_folder_path + filename)
  
  
# ! Init Haroun :

# Execute if run as script. 
if __name__ == "__main__":

  # Unpack.
  unpack(PACK_PATH)
  
  # Pack.
  pack(PACK_PATH)
  