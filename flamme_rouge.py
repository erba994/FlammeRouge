#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Compatibility layer for the modular Flamme Rouge implementation.

This file provides backward compatibility by importing all the necessary
components from the modular structure and exposing them as if they were
in the original single file. This allows existing code to continue working
while transitioning to the new modular architecture.

For new development, import directly from the specific modules:
- models: Game data structures and enums
- game: Track logic and display functionality  
- player: Player implementations and AI strategies
- network: Client interfaces and networking
- config: Configuration and course management
- main: Main game coordination and entry point
"""

# Re-export all components for backward compatibility
from models import *
from game import *
from player import *
from network import *
from config import *
from main import *

if __name__ == "__main__":
    # Delegate to main module
    from main import parse_arguments, principal, client_console, show_help
    import sys
    import logging
    
    logging.basicConfig(level=logging.WARNING)
    
    args_result = parse_arguments()
    
    if args_result is None:
        sys.exit(0)
    
    nb_humains, display_mode, is_client, client_args = args_result
    
    if is_client and client_args is not None:
        client_console(*client_args)
    elif nb_humains is not None and display_mode is not None:
        principal(nb_humains, display_mode)
    else:
        show_help()
        sys.exit(1)
