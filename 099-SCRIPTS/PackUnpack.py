# ! Imports :

# Imports from module os and os.path
from os import listdir, mkdir, rename, walk, rmdir, remove
from os.path import isfile, isdir, join, basename, splitext, dirname, abspath
from re import split

# Defines all paths.
ROOT_PATH = f"N:/A TRIER/"
PACK_PATH = f"{ROOT_PATH}0001/"
MOVIES_PATH = f"{ROOT_PATH}001 FILMS/"

# Liste d'extensions de fichiers à supprimer 
REMOVE_EXTS = [".jpg", ".jpeg", ".png", ".nfo", ".txt"]
AUTHORIZED_EXTS = [".avi", ".mkv", ".mp4", ".srt", ".sub"]

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
  
  # Ajout d'un espace en début et fin de nom de fichier pour faciliter le match des mots à retirer
  root = f" {root} "
  
  # Liste de caractères à retirer des noms de fichiers. 
  chars_to_delete = [
    "5.1", 
    "4.0", 
    ".", 
    "-", 
    "_", 
    "[", 
    "]", 
    "{", 
    "}", 
    "~", 
    "+", 
    "(", 
    ")", 
    "!", 
  ]
  
  # Liste de mots à retirer des noms de fichiers. 
  words_to_delete = [
    "(fasandraeberne)",
    "(flaskepost fra p)",
    "(kvinden i buret)",
    "\'extended version\'", 
    "1080", 
    "1080i", 
    "1080p",
    "10bit",
    "1920x1080",
    "2160p", 
    "480p", 
    "4klight",
    "6ch", 
    "720p",
    "Portos",
    "custom",
    "gbx",
    "bit",
    "gwen",
    "2vf",
    "version non censurée",
    "mm91",
    "libertad",
    "tf",
    "hdl",
    "multi3",
    "eaulive",
    "aac",
    "aaclc",
    "abcollection",
    "ac3",
    "ac 3", 
    "acc",
    "amzn", 
    "ark01",
    "avc", 
    "bbc", 
    "bdrip",
    "bluray",
    "bluray1080p",
    "brrip",
    "ccats", 
    "chris44",
    "ddp", 
    "dl", 
    "directors cut",
    "dolby vision",
    "dread team", 
    "dts",
    "dvdrip",
    "dvd rip", 
    "en",
    "eng",
    "extended",
    "extreme",
    "final cut",
    "hush",
    "zeusfaber",
    "zone80",
    "darkjuju",
    "webdl",
    "vlis",
    "vost",
    "benh4",
    "vostfr",
    "stereo",
    "title1",
    "dd",
    "lazarus",
    "acool",
    "nobodyperfect",
    "fr",
    "fre",
    "french",
    "french(vff)", 
    "frosties",
    "ght",
    "ghz",
    "gismo65",
    "h264",
    "h265",
    "h4s5s", 
    "hd", 
    "hdlight",
    "hdma",
    "hdr",
    "hdtv",
    "he",
    "hevc",
    "integral",
    "integrale",
    "internal",
    "jiheff",
    "k7", 
    "kfl",
    "lcds",
    "luminus",
    "mhd",
    "mhdgz",
    "mkv",
    "moe", 
    "mtl666", 
    "multi",
    "nf", 
    "noex",
    "notag",
    "nyu", 
    "owii",
    "p4t4t3", 
    "pop", 
    "pophd",
    "portos", 
    "qtz",
    "remastered",
    "romkent",
    "se7en", 
    "shc23",
    "srt", 
    "tr", 
    "truefrench",
    "trunkdu92",
    "tonyk", 
    "tvwh0res",
    "unrated",
    "uptopol",
    "utt", 
    "vf",
    "vf2",
    "vff",
    "vfi",
    "vfq",
    "vmpp",
    "vmpp",
    "vo", 
    "vof", 
    "web dl",
    "web",
    "webrip", 
    "x264",
    "x265",
    "xvid",
    "zza",
  ]
  
  # Affichage des words_to_delete dans l'ordre alphabétique
#   words_to_delete.sort()
#   for word in words_to_delete: 
#     print(f"\"{word}\", ")
#   exit() 
  
  # Remplacement des charactères par un espace.
  for char in chars_to_delete: 
    # Si charactère non vide.
    if char :
      # Remplacement du charactère par un espace.
      root = root.replace(char, " ")
  
  # Retrait des mots.
  for word in words_to_delete:
    # Si mot non vide.
    if word :
      # Remplacement du mot précédé et suivit d'un espace par un espace simple.
      root = root.replace(f" {word} ", " ")
    
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
    # print(f"Traitement du dossier : {main_folder_path} => {isdir(main_folder_path)}")
    
    # Pour chaque dossier dans l'ensemble des sous-dossiers de niveau 1 présents dans le dossier principal  
    for dir_name in dirs: 
      
      # Chemin complet du sous-dossier.
      sub_folder_path =  main_folder_path + dir_name + "/"
      
      # Affichage debug 
      # print(f"Sous-dossier : {sub_folder_path} => {isdir(sub_folder_path)}")
      
      # Parcours sub_folder_path et déplace les fichiers à la racine 
      unpack(sub_folder_path, True) 
  
  # Parcours des dossiers et fichiers présents dans le dossier et création d'une liste des dossiers et une liste des fichiers 
  for path, dirs, files in walk(main_folder_path):
  
    # Parcours les fichiers de main_folder_path
    for filename in files:
  
      # Récupération de l'extension
      root, extension = splitext(filename)

  
      # Nettoyage du nom de fichier d'arrivée.
      filename_cleaned = clean_name(filename)
      
      # Chemin de fichier de départ.
      old_file_path = main_folder_path + filename
      
      # Affichage debug 
      # print("------------------------------------------------")
      # print(f"{old_file_path} => {isfile(old_file_path)} ")

      # Traitement des fichiers quand treat_files est vrai.
      if treat_files is True: 
        # Chemin de fichier d'arrivée (dossier parent + nettoyage du nom de fichier) 
        new_file_path = main_folder_path_parent + filename_cleaned
      # Si pas de dossier parent.
      else:
        # Chemin de fichier d'arrivée (dossier actuel + nettoyage du nom de fichier)
        new_file_path = main_folder_path + filename_cleaned
      
      # Si dry_run est faux. 
      if DRY_RUN is False: 
        # Vérification si extension dans liste d'extensions à supprimer 
        if extension.lower() in REMOVE_EXTS: 
          # Suppression du fichier 
          remove(old_file_path)
        else:  
          # Renomme le fichier et déplacement dans le dossier parent si nécessaire 
          rename(old_file_path, new_file_path)
      
      # Vérification si extension dans liste d'extensions à supprimer 
      if extension.lower() in REMOVE_EXTS: 
        # Affichage debug 
        print("")
        print(f"Remove => {old_file_path}")
        print("")
        print("------------------------------------------------")
      else:
        # Affichage debug 
        print("")
        print(f"{old_file_path}")
        print("=>")
        print(f"{new_file_path}")
        print("")
        print("------------------------------------------------")
      
      # Recherche d'extensions non gérées 
      if extension not in REMOVE_EXTS and extension not in AUTHORIZED_EXTS: 
        print(f"Extension non gérée: {extension}")
     
  # Si le déplacement des fichiers vers le parent à eu lieu et dry_run est faux.
  if treat_files is True and DRY_RUN is False: 
    # Suppression du dossier vidé 
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
      # print(f"Pack : {filename}")
      # Création d'un dossier nommé comme le nom de fichier si dry_run est faux.
      if DRY_RUN is False :
        # Vérification si le dossier existe déjà 
        if not isdir(file_folder_path): 
          mkdir(file_folder_path)
        # Déplacement du fichier vers le nouveau dossier créer.
        rename(main_folder_path + filename, file_folder_path + filename)
  
  
# ! Init :

# Execute if run as script. 
if __name__ == "__main__":

  # Unpack.
  unpack(PACK_PATH)
  
  # Pack.
  pack(PACK_PATH)
  