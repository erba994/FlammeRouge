#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Main entry point for Flamme Rouge cycling game.

This module provides the main game coordination:
- Command-line argument parsing
- Game setup and player initialization
- Main game loop coordination
- Help system and display mode management
"""

import logging
import os.path
import random
import socket
import sys
import threading
import time

from config import choisir_course, load_game_config
from models import Profil, Pion
from network import Console, ClientNul, client_console
from player import Humain, Robot, Robourrin, Robomou, Rofinot


def principal(nb_humains, display_mode='window'):
    """Main game function that orchestrates the complete race.
    
    Args:
        nb_humains (int): Number of human players (1-4)
        display_mode (str): Display mode for track visualization
    """
    # Load course and configuration
    tracé, nb_tours = choisir_course(
        os.path.join(os.path.dirname(sys.argv[0]), "courses.json"))

    config_path = os.path.join(os.path.dirname(sys.argv[0]), "game_config.yaml")
    config = load_game_config(config_path)
    
    # Initialize players
    joueurs = _setup_players(config, nb_tours, display_mode)
    
    # Set player colors
    for joueur in joueurs:
        joueur.client.couleur(joueur.couleur)

    # Starting positions
    _setup_starting_positions(tracé, joueurs)

    # Main race loop
    _run_race(tracé, joueurs)


def _setup_players(config, nb_tours, display_mode):
    """Set up all players (human and AI) for the game.
    
    Args:
        config (dict): Game configuration
        nb_tours (int): Number of race laps
        display_mode (str): Display mode for human players
        
    Returns:
        list: List of initialized player objects
    """
    joueurs = []
    robot_classes = [Robot, Robourrin, Robomou, Rofinot]
    
    for team in config.get("teams", []):
        color = team.get("color", "unknown")
        yaml_path = team.get("yaml")
        team_type = team.get("type", "robot")
        
        if team_type == "human":
            console = Console(display_mode)
            joueurs.append(Humain(color, yaml_path, nb_tours, console))
        else:
            robot_class = random.choice(robot_classes)
            player = robot_class(color, yaml_path, nb_tours)
            player.client = ClientNul()
            joueurs.append(player)
    
    return joueurs


def _setup_starting_positions(tracé, joueurs):
    """Handle the starting position phase of the race.
    
    Args:
        tracé (Tracé): The race track
        joueurs (list): List of all players
    """
    joueurs[0].client.afficher(tracé, 0, tracé.départ)
    
    for joueur in joueurs:
        # Show waiting message to other players
        for joueur_en_attente in joueurs:
            if joueur_en_attente is not joueur:
                color_name = joueur.couleur if isinstance(joueur.couleur, str) else joueur.couleur.name
                joueur_en_attente.client.attente(list([color_name]))
        
        # Get position selection
        paire = joueur.placer(tracé)
        
        # Place riders on track
        if paire.sprinteur >= paire.rouleur:
            pion = Pion(Profil.sprinteur, joueur)
            tracé.poser(pion, paire.sprinteur)
            pion = Pion(Profil.rouleur, joueur)
            tracé.poser(pion, paire.rouleur)
        else:
            pion = Pion(Profil.rouleur, joueur)
            tracé.poser(pion, paire.rouleur)
            pion = Pion(Profil.sprinteur, joueur)
            tracé.poser(pion, paire.sprinteur)
        
        # Update display for all players
        for joueur_en_attente in joueurs:
            joueur_en_attente.client.afficher(tracé, 0, tracé.départ)


def _run_race(tracé, joueurs):
    """Execute the main race loop until completion.
    
    Args:
        tracé (Tracé): The race track
        joueurs (list): List of all players
    """
    fin_de_partie = False
    
    while not fin_de_partie:
        # Energy selection phase
        paires = _collect_energy_choices(tracé, joueurs)

        # Movement phase
        tracé.déplacer(paires)

        # Slipstream phase
        tracé.aspirer(joueurs)
        
        # Show updated track after movement and aspiration
        for joueur in joueurs:
            joueur.client.afficher(tracé)
        
        # Fatigue phase (without showing track again)
        fatigués = tracé.fatiguer()
        for joueur in joueurs:
            joueur.client.afficher_fatigue(tracé, fatigués)

        # Check for race completion
        fin_de_partie = (max(tracé.positions.values()) >= tracé.arrivée)

    # Display final results
    for joueur in joueurs:
        joueur.client.afficher(tracé)
        joueur.client.ordre(tracé.ordre())


def _collect_energy_choices(tracé, joueurs):
    """Collect energy card choices from all players using threading.
    
    Args:
        tracé (Tracé): The race track
        joueurs (list): List of all players
        
    Returns:
        dict: Map of player -> energy choice pairs
    """
    paires = dict()
    tâches = dict()

    # Start threads for player decisions
    for joueur in joueurs:
        if (joueur not in paires and
                (joueur not in tâches or not tâches[joueur].is_alive())):
            tâches[joueur] = threading.Thread(
                target=lambda t, j, p: p.update([(j, j.jouer(t))]),
                args=(tracé, joueur, paires))
            tâches[joueur].start()

    # Wait for all decisions with status updates
    attendre_couleurs_precedentes = list(
        map(lambda j: j.couleur if isinstance(j.couleur, str) else j.couleur.name, joueurs))
    
    while True:
        time.sleep(1)
        attendre_couleurs = list()
        for joueur in joueurs:
            if joueur not in paires:
                color_name = joueur.couleur if isinstance(joueur.couleur, str) else joueur.couleur.name
                attendre_couleurs.append(color_name)
        
        if not attendre_couleurs:
            break
        else:
            if len([c for c in attendre_couleurs_precedentes if c not in attendre_couleurs]):
                for joueur in paires.keys():
                    joueur.client.attente(attendre_couleurs)
                attendre_couleurs_precedentes = list(attendre_couleurs)

    return paires


def show_help():
    """Display comprehensive help information."""
    print("Flamme Rouge - Cycling Race Game")
    print("Usage: python3 flamme_rouge.py [OPTIONS]")
    print()
    print("Options:")
    print("  -h <num>         Number of human players (1-4, default: 1)")
    print("  -d <mode>        Display mode (default: window)")
    print("  --display <mode> Display mode (same as -d)")
    print("  --help           Show this help message")
    print()
    print("Display Modes:")
    print("  window    Original windowed view showing current race area")
    print("  full      Complete track in single view (wraps if too wide)")
    print("  wrapped   Multi-line display for very long tracks")
    print("  overview  Compressed overview with detailed current section")
    print()
    print("Examples:")
    print("  python3 flamme_rouge.py")
    print("  python3 flamme_rouge.py -d full")
    print("  python3 flamme_rouge.py --display wrapped")
    print("  python3 flamme_rouge.py -h 2 -d overview")
    print("  python3 flamme_rouge.py full  # Direct mode specification")
    print()
    print("Client Mode:")
    print("  python3 flamme_rouge.py <port>")
    print("  python3 flamme_rouge.py -c <host> <port>")


def parse_arguments():
    """Parse command-line arguments and return configuration.
    
    Returns:
        tuple: (nb_humains, display_mode, client_mode, client_args) or None for help
    """
    # Check for help
    if '--help' in sys.argv or 'help' in sys.argv:
        show_help()
        return None
    
    # Parse command-line arguments for display mode
    display_mode = 'overview'  # default
    valid_modes = ['window', 'full', 'wrapped', 'overview']
    nb_humains = 1
    
    # Check for client mode
    if len(sys.argv) == 2 or (len(sys.argv) > 2 and sys.argv[1] == '-c'):
        if len(sys.argv) == 3:
            return None, None, True, (socket.gethostname(), int(sys.argv[2]))
        elif len(sys.argv) == 4:
            return None, None, True, (sys.argv[2], int(sys.argv[3]))
        else:
            return None, None, True, (socket.gethostname(), int(sys.argv[1]))
    
    # Parse server mode arguments
    args = sys.argv[1:]
    
    # Check for display mode argument
    if '-d' in args or '--display' in args:
        try:
            display_idx = args.index('-d') if '-d' in args else args.index('--display')
            if display_idx + 1 < len(args):
                mode = args[display_idx + 1]
                if mode in valid_modes:
                    display_mode = mode
                    print(f"Display mode set to: {display_mode}")
                else:
                    print(f"Invalid display mode '{mode}'. Valid modes: {', '.join(valid_modes)}")
                    print("Using default 'overview' mode.")
        except (ValueError, IndexError):
            print("Display mode argument error. Using default 'overview' mode.")
    
    # Check for direct mode argument (backward compatibility)
    for arg in args:
        if arg in valid_modes:
            display_mode = arg
            print(f"Display mode set to: {display_mode}")
            break
    
    # Check for human players argument
    if '-h' in args:
        try:
            h_idx = args.index('-h')
            if h_idx + 1 < len(args):
                nb_humains = min(4, max(1, int(args[h_idx + 1])))
        except (ValueError, IndexError):
            pass
    
    return nb_humains, display_mode, False, None


if __name__ == "__main__":
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
