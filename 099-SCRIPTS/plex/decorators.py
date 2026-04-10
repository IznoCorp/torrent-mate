#!/usr/bin/env python
# -*- coding: utf-8 -*-
#

""" Importing libraries """

import os
import time
import pickle
from functools import wraps
from hashlib import md5

""" Decorators """

def timeit(debug = True, precision = 5):

    """ Decorator to time a function """

    def timed(method):
        @wraps(method)
        def warper(*args, **kw):
            ts = time.time()
            result = method(*args, **kw)
            te = time.time()
            if debug :
                print(f"{method.__name__} : {round(te-ts, precision)} sec")
            return result
        return warper
    return timed

def cacheit(cache_max_age = 86400, debug = False, cache_file_prefix = "cache_", reset_cache = False):

    """ 
        Decorator to cache a function. 
        The cache is stored in a file.
        The cache is valid for cache_max_age seconds.
        ---
        Parameters
            cache_max_age : int
                The cache is valid for cache_max_age seconds.
            debug : Boolean
                If true, print debug information.
            cache_file_prefix : String
                The cache file prefix.
            reset_cache : Boolean
                If true, reset the cache.
    """

    def cached(method):
        @wraps(method)
        def warper(*args, **kwargs):           

            # Method name.
            method_name = method.__name__

            # Main script path.
            root_path = os.path.dirname(os.path.abspath(__file__))

            # Cache file path.
            cache_file_path = f"{root_path}/__pycache__/{cache_file_prefix}{method_name}.pkl"

            # Caches loaded flags.
            caches_loaded = {}

            # Create cache loaded flag default value.
            if method_name not in caches_loaded:
                caches_loaded[method_name] = False

            # Caches dict.
            caches = {}

            # Check if the cache have to be reset.
            if reset_cache:
                # Delete the cache file.
                os.remove(cache_file_path)
                # Reset the cache loaded flag.
                caches_loaded[method_name] = False     

            # Check if the cache is loaded and cache file exists
            if not caches_loaded[method_name] and os.path.isfile(cache_file_path):
                # Check if file creation date is greater than cache_max_age in seconds.
                if time.time() - os.path.getctime(cache_file_path) < cache_max_age:
                    # Read the cache file.
                    with open(cache_file_path, "rb") as cache_file:
                        # Load the cache.
                        caches[method_name] = pickle.load(cache_file)
                    # Cache loaded.
                    caches_loaded[method_name] = True
                else:
                    # Delete the cache file.
                    os.remove(cache_file_path)
            
            # If no cache found.
            if not caches_loaded[method_name]: 
                # Define a new cache.
                caches[method_name] = {}
                if debug :
                    # Print cache reset.
                    print(f"Cache for method {method_name} have been reset.")
            
            # Get the method call args.
            method_call_args = args

            # Create call key with method args.
            args_md5 = md5()
            for arg in method_call_args:
                args_md5.update(str(arg).encode())
            # Get Hexadecimal format of the hash.
            method_call_key = args_md5.hexdigest()

            # Check if the method call is in the cache.
            if method_call_key in caches[method_name]:
                if debug :
                    # Print use the cached result.
                    print(f" - Use cached result for method call {method_name}({method_call_args}) [{method_call_key}]")
                # Return the cached result.
                result = caches[method_name][method_call_key]
            else:
                # Call the method.
                result = method(*args, **kwargs)
                if debug :
                    # Print set in cache.
                    print(f" - Method call {method_name}({method_call_args}) set in cache. [{method_call_key}]")
                # Add the result to the cache.
                caches[method_name][method_call_key] = result
                # Save the cache.
                with open(cache_file_path, "wb") as cache_file:
                    pickle.dump(caches[method_name], cache_file)
                
            # Return the result.
            return result
        return warper
    return cached
