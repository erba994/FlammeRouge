#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Configuration and course management for Flamme Rouge.

This module handles:
- Course selection and loading from JSON files
- Game configuration validation
- Track construction from course definitions
- Team setup and configuration management
"""

import json
import logging
import os.path

from models import Case, Pente
from game import Tracé


def choisir_course(chemin):
    """Choose and construct a race course from configuration file.
    
    Args:
        chemin (str): Path to the courses JSON file
        
    Returns:
        tuple: (Tracé object, number of laps)
    """
    # Read configuration file
    parcours = None
    with open(chemin, "rt", encoding="utf-8") as entrée:
        parcours = json.load(entrée)

    # Validate configuration
    _validate_parcours(parcours)

    # Let user choose course
    course_name = _interactive_course_selection(parcours)
    
    # Build the selected course
    return _construct_course(parcours, course_name)


def _validate_parcours(parcours):
    """Validate the course configuration for consistency.
    
    Args:
        parcours (dict): Course configuration data
    """
    # Validate cases
    for nom_case, case in parcours["cases"].items():
        if not ("angle" in case and "pente" in case):
            logging.error(f"Case {nom_case} incohérente")

    # Validate tronçons
    for nom_tronçon, tronçon in parcours["tronçons"].items():
        if tronçon is None:
            logging.warning(f"Tronçon {nom_tronçon} non déterminé")
        else:
            if len(tronçon) not in [2, 6]:
                logging.error(f"Tronçon {nom_tronçon} incohérent")
            for nom_case in tronçon:
                if nom_case not in parcours["cases"]:
                    logging.error(
                        f"Case inconnue dans tronçon «{nom_tronçon}»")

    # Validate courses
    for nom_course, course in parcours["courses"].items():
        for nom_tronçon in course["tracé"]:
            if nom_tronçon not in parcours["tronçons"]:
                logging.error(f"Tronçon inconnu dans la course «{nom_course}»")
            elif parcours["tronçons"][nom_tronçon] is None:
                logging.error(f"La course «{nom_course}» référence le tronçon "
                              f"«{nom_tronçon}»")
            elif nom_tronçon.swapcase() in course["tracé"]:
                logging.error(f"Le tronçon «{nom_tronçon}» est référencé sous "
                              "plusieurs formes dans la course "
                              f"«{nom_course}»")
            elif course["tracé"].count(nom_tronçon) > 1:
                logging.error(f"Le tronçon «{nom_tronçon}» est référencé "
                              f"plusieurs fois dans la course «{nom_course}»")


def _interactive_course_selection(parcours):
    """Present course options to user for selection.
    
    Args:
        parcours (dict): Course configuration data
        
    Returns:
        str: Selected course name
    """
    noms = sorted(parcours["courses"])
    for i, nom_course in enumerate(noms):
        print("{}) {}".format(i + 1, nom_course))
    
    while True:
        try:
            i = int(input("Choix du parcours ? ")) - 1
            if 0 <= i < len(noms):
                return noms[i]
        except ValueError:
            pass


def _construct_course(parcours, nom_course):
    """Construct a race track from course definition.
    
    Args:
        parcours (dict): Course configuration data
        nom_course (str): Name of the course to construct
        
    Returns:
        tuple: (Tracé object, number of laps)
    """
    cases = list()
    départ = None
    arrivée = None
    course = parcours["courses"][nom_course]
    nb_tours = course["tours"]
    tronçons = course["tracé"]
    
    # Build track cases
    for i in range(nb_tours):
        for nom_tronçon in tronçons:
            for nom_case in parcours["tronçons"][nom_tronçon]:
                case = parcours["cases"][nom_case]
                if case["pente"] == 0:
                    cases.append(Case(Pente.plat))
                elif case["pente"] == 1:
                    cases.append(Case(Pente.col))
                else:  # case["pente"] == -1
                    cases.append(Case(Pente.descente))

                if nom_case == "départ":
                    départ = len(cases)
                elif nom_case == "arrivée" and arrivée is None:
                    arrivée = len(cases) - 1
    
    # Handle start/finish positioning
    if nb_tours == 1:
        if départ is not None and arrivée is not None:
            lg_circuit = arrivée - départ
        else:
            lg_circuit = len(cases)
    else:
        lg_circuit = len(cases) / nb_tours
        départ = 0
        t_arrivée = tronçons[-1]
        for nom_case in parcours["tronçons"][t_arrivée]:
            if nom_case == "arrivée":
                cases = [Case(Pente.plat)] + cases
                départ += 1

        arrivée = len(cases)
        t_départ = tronçons[0]
        for nom_case in parcours["tronçons"][t_départ]:
            if nom_case == "départ":
                cases += [Case(Pente.plat)]

    # Ensure valid start and finish positions
    if départ is None:
        départ = 0
    if arrivée is None:
        arrivée = len(cases) - 1

    tracé = Tracé(cases, départ, arrivée, lg_circuit)
    return tracé, nb_tours


def load_game_config(config_path):
    """Load game configuration from YAML file.
    
    Args:
        config_path (str): Path to game configuration file
        
    Returns:
        dict: Game configuration data
    """
    import yaml
    
    if not os.path.exists(config_path):
        # Return default configuration if file doesn't exist
        return {
            "teams": [
                {"color": "bleu", "yaml": "teams/team_bleu.yaml", "type": "human"},
                {"color": "noir", "yaml": "teams/team_noir.yaml", "type": "robot"},
                {"color": "gris", "yaml": "teams/team_gris.yaml", "type": "robot"},
                {"color": "vert", "yaml": "teams/team_vert.yaml", "type": "robot"}
            ]
        }
    
    with open(config_path, "r") as f:
        return yaml.safe_load(f)


def validate_team_config(team_yaml_path):
    """Validate team configuration file.
    
    Args:
        team_yaml_path (str): Path to team YAML file
        
    Returns:
        bool: True if configuration is valid
    """
    import yaml
    
    if not os.path.exists(team_yaml_path):
        logging.warning(f"Team configuration file not found: {team_yaml_path}")
        return False
    
    try:
        with open(team_yaml_path, 'r') as f:
            team_cfg = yaml.safe_load(f)
        
        # Check required fields
        if 'sprinteur' not in team_cfg or 'rouleur' not in team_cfg:
            logging.error(f"Team config missing required fields: {team_yaml_path}")
            return False
        
        # Validate card lists
        for rider_type in ['sprinteur', 'rouleur']:
            cards = team_cfg[rider_type]
            if not isinstance(cards, list) or len(cards) == 0:
                logging.error(f"Invalid {rider_type} card list in {team_yaml_path}")
                return False
            
            # Check if all cards are valid integers
            for card in cards:
                if not isinstance(card, int) or card < 2 or card > 9:
                    logging.error(f"Invalid card value {card} in {team_yaml_path}")
                    return False
        
        return True
        
    except Exception as e:
        logging.error(f"Error validating team config {team_yaml_path}: {e}")
        return False
