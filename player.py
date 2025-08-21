#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Player implementations and AI strategies for Flamme Rouge.

This module contains all player types including:
- Base player class with deck management
- Human player with client interaction
- AI robots with different strategies
- Card drawing and fatigue mechanics
"""

import random
import yaml

from models import Profil, Paire, Pion, Pente


class Joueur:
    """Base player class with common deck management functionality."""
    
    def __init__(self, couleur, team_yaml_path, nb_tours):
        """Initialize a player with their team configuration.
        
        Args:
            couleur (str): Player's team color
            team_yaml_path (str): Path to team configuration YAML file
            nb_tours (int): Number of laps in the race
        """
        # Load team configuration from YAML file
        with open(team_yaml_path, 'r') as f:
            team_cfg = yaml.safe_load(f)
        self.couleur = couleur
        self.client = None  # Will be set by subclasses
        self.sprinteur = nb_tours * team_cfg.get('sprinteur', [])
        self.rouleur = nb_tours * team_cfg.get('rouleur', [])
        self.défausse_sprinteur = []
        self.défausse_rouleur = []
        random.shuffle(self.sprinteur)
        random.shuffle(self.rouleur)

    def placer(self, tracé):
        """Provide positions for placement on the starting line.
        
        Args:
            tracé (Tracé): The race track
            
        Returns:
            Paire: Positions for sprinter and rouleur
        """
        raise NotImplementedError

    def jouer(self, tracé):
        """Provide energy cards for both riders.
        
        Args:
            tracé (Tracé): The race track
            
        Returns:
            Paire: Energy values for sprinter and rouleur
        """
        raise NotImplementedError

    def _piocher(self, tas, défausse):
        """Draw 4 cards from deck, reshuffling discard pile if needed.
        
        Args:
            tas (list): Current deck
            défausse (list): Discard pile
            
        Returns:
            list: 4 energy cards to choose from
        """
        if len(tas) < 4:
            random.shuffle(défausse)
            tas.extend(défausse)
            défausse.clear()
        if len(tas) == 0:
            tas.append(2)

        retour = tas[:4]
        tas[:] = tas[4:]

        return retour


class Humain(Joueur):
    """Human player that interacts through a client interface."""
    
    def __init__(self, couleur, team_yaml_path, nb_tours, client):
        """Initialize human player with client interface.
        
        Args:
            couleur (str): Player's team color
            team_yaml_path (str): Path to team configuration YAML
            nb_tours (int): Number of race laps
            client (Client): User interface client
        """
        super().__init__(couleur, team_yaml_path, nb_tours)
        self.client = client

    def placer(self, tracé):
        """Interactive starting position selection.
        
        Args:
            tracé (Tracé): The race track
            
        Returns:
            Paire: Selected positions for both riders
        """
        libres = list()
        for i in range(tracé.départ):
            case = tracé.cases[i]
            if case.gauche is None:
                libres.append(i)
            if case.droite is None:
                libres.append(i)

        while True:
            positions = self.client.demander_positions(tracé, libres)
            try:
                libres_temp = list(libres)
                sprinteur = int(positions.sprinteur)
                rouleur = int(positions.rouleur)
                libres_temp.remove(sprinteur)
                libres_temp.remove(rouleur)
            except ValueError:
                pass
            break

        return positions

    def jouer(self, tracé):
        """Interactive energy card selection.
        
        Args:
            tracé (Tracé): The race track
            
        Returns:
            Paire: Selected energy cards for both riders
        """
        énergies_sprinteur = sorted(
            self._piocher(self.sprinteur, self.défausse_sprinteur))
        énergies_rouleur = sorted(
            self._piocher(self.rouleur, self.défausse_rouleur))

        while True:
            choix = self.client.demander_jeu(list(énergies_sprinteur),
                                             list(énergies_rouleur))
            try:
                sprinteur = int(choix.sprinteur)
                rouleur = int(choix.rouleur)
                énergies_sprinteur.remove(sprinteur)
                énergies_rouleur.remove(rouleur)
            except ValueError:
                pass
            break

        self.défausse_sprinteur.extend(énergies_sprinteur)
        self.défausse_rouleur.extend(énergies_rouleur)

        return choix


class Robot(Joueur):
    """AI robot that plays randomly."""

    def __init__(self, couleur, team_yaml_path, nb_tours):
        """Initialize random AI robot.
        
        Args:
            couleur (str): Player's team color
            team_yaml_path (str): Path to team configuration YAML
            nb_tours (int): Number of race laps
        """
        super().__init__(couleur, team_yaml_path, nb_tours)

    def placer(self, tracé):
        """Random starting position selection.
        
        Args:
            tracé (Tracé): The race track
            
        Returns:
            Paire: Random positions for both riders
        """
        libres = list()
        for i in range(tracé.départ):
            case = tracé.cases[i]
            if case.gauche is None:
                libres.append(i)
            if case.droite is None:
                libres.append(i)
        sprinteur, rouleur = random.sample(libres, 2)
        return Paire(sprinteur, rouleur)

    def jouer(self, tracé):
        """Random energy card selection.
        
        Args:
            tracé (Tracé): The race track
            
        Returns:
            Paire: Random energy cards for both riders
        """
        énergies_sprinteur = self._piocher(self.sprinteur,
                                           self.défausse_sprinteur)
        énergies_rouleur = self._piocher(self.rouleur, self.défausse_rouleur)

        sprinteur = random.sample(énergies_sprinteur, 1)[0]
        rouleur = random.sample(énergies_rouleur, 1)[0]

        énergies_sprinteur.remove(sprinteur)
        énergies_rouleur.remove(rouleur)

        self.défausse_sprinteur.extend(énergies_sprinteur)
        self.défausse_rouleur.extend(énergies_rouleur)

        return Paire(sprinteur, rouleur)


class Robomou(Robot):
    """Smart AI robot that avoids fatigue based on terrain ahead."""

    def __init__(self, couleur, team_yaml_path, nb_tours):
        """Initialize terrain-aware AI robot.
        
        Args:
            couleur (str): Player's team color
            team_yaml_path (str): Path to team configuration YAML
            nb_tours (int): Number of race laps
        """
        super().__init__(couleur, team_yaml_path, nb_tours)

    def jouer(self, tracé):
        """Terrain-aware energy card selection.
        
        Args:
            tracé (Tracé): The race track
            
        Returns:
            Paire: Strategic energy cards for both riders
        """
        énergies_sprinteur = self._piocher(self.sprinteur,
                                           self.défausse_sprinteur)
        énergies_rouleur = self._piocher(self.rouleur, self.défausse_rouleur)

        # Random play but avoid excessive fatigue
        index_sprinteur = tracé.positions[Pion(Profil.sprinteur, self)]
        index_rouleur = tracé.positions[Pion(Profil.rouleur, self)]

        if tracé.cases[index_sprinteur].pente == Pente.descente:
            sprinteur = min(énergies_sprinteur)
        else:
            for d in range(1, 10):
                if tracé.cases[index_sprinteur + d].pente == Pente.col:
                    if d <= 5:
                        max_sprinteur = 5
                    else:
                        max_sprinteur = d - 1

                    és = [é for é in énergies_sprinteur if é <= max_sprinteur]
                    if len(és) == 0:
                        és = [min(énergies_sprinteur)]
                    break
            else:
                és = énergies_sprinteur
            sprinteur = random.sample(és, 1)[0]

        if tracé.cases[index_rouleur].pente == Pente.descente:
            rouleur = min(énergies_rouleur)
        else:
            for d in range(1, 10):
                if tracé.cases[index_rouleur + d].pente == Pente.col:
                    if d <= 5:
                        max_rouleur = 5
                    else:
                        max_rouleur = d - 1

                    és = [é for é in énergies_rouleur if é <= max_rouleur]
                    if len(és) == 0:
                        és = [min(énergies_rouleur)]
                    break
            else:
                és = énergies_rouleur
            rouleur = random.sample(és, 1)[0]

        énergies_sprinteur.remove(sprinteur)
        énergies_rouleur.remove(rouleur)

        self.défausse_sprinteur.extend(énergies_sprinteur)
        self.défausse_rouleur.extend(énergies_rouleur)

        return Paire(sprinteur, rouleur)


class Robourrin(Joueur):
    """Aggressive AI robot that always plays maximum energy."""

    def __init__(self, couleur, team_yaml_path, nb_tours):
        """Initialize aggressive AI robot.
        
        Args:
            couleur (str): Player's team color
            team_yaml_path (str): Path to team configuration YAML
            nb_tours (int): Number of race laps
        """
        super().__init__(couleur, team_yaml_path, nb_tours)

    def placer(self, tracé):
        """Place both riders at front of starting line.
        
        Args:
            tracé (Tracé): The race track
            
        Returns:
            Paire: Front positions for both riders
        """
        return Paire(tracé.départ - 1, tracé.départ - 1)

    def jouer(self, tracé):
        """Always play maximum available energy.
        
        Args:
            tracé (Tracé): The race track
            
        Returns:
            Paire: Maximum energy cards for both riders
        """
        énergies_sprinteur = self._piocher(self.sprinteur,
                                           self.défausse_sprinteur)
        énergies_rouleur = self._piocher(self.rouleur, self.défausse_rouleur)

        sprinteur = max(énergies_sprinteur)
        rouleur = max(énergies_rouleur)

        énergies_sprinteur.remove(sprinteur)
        énergies_rouleur.remove(rouleur)

        self.défausse_sprinteur.extend(énergies_sprinteur)
        self.défausse_rouleur.extend(énergies_rouleur)

        return Paire(sprinteur, rouleur)


class Rofinot(Joueur):
    """Strategic aggressive AI that avoids fatigue while playing strong."""

    def __init__(self, couleur, team_yaml_path, nb_tours):
        """Initialize strategic AI robot.
        
        Args:
            couleur (str): Player's team color
            team_yaml_path (str): Path to team configuration YAML
            nb_tours (int): Number of race laps
        """
        super().__init__(couleur, team_yaml_path, nb_tours)

    def placer(self, tracé):
        """Place both riders at front of starting line.
        
        Args:
            tracé (Tracé): The race track
            
        Returns:
            Paire: Front positions for both riders
        """
        return Paire(tracé.départ - 1, tracé.départ - 1)

    def jouer(self, tracé):
        """Play maximum energy while avoiding fatigue on climbs.
        
        Args:
            tracé (Tracé): The race track
            
        Returns:
            Paire: Strategic energy cards for both riders
        """
        énergies_sprinteur = self._piocher(self.sprinteur,
                                           self.défausse_sprinteur)
        énergies_rouleur = self._piocher(self.rouleur, self.défausse_rouleur)

        # Aggressive but avoid excessive fatigue
        index_sprinteur = tracé.positions[Pion(Profil.sprinteur, self)]
        index_rouleur = tracé.positions[Pion(Profil.rouleur, self)]

        if tracé.cases[index_sprinteur].pente == Pente.descente:
            sprinteur = min(énergies_sprinteur)
        else:
            és = énergies_sprinteur  # Default to all energies
            for d in range(1, 10):
                # Check if the position is within track bounds
                if index_sprinteur + d >= len(tracé.cases):
                    break
                if tracé.cases[index_sprinteur + d].pente == Pente.col:
                    if d <= 5:
                        max_sprinteur = 5
                    else:
                        max_sprinteur = d - 1

                    és = [é for é in énergies_sprinteur if é <= max_sprinteur]
                    if len(és) == 0:
                        és = [min(énergies_sprinteur)]
                    break
            sprinteur = max(és)

        if tracé.cases[index_rouleur].pente == Pente.descente:
            rouleur = min(énergies_rouleur)
        else:
            ér = énergies_rouleur  # Default to all energies
            for d in range(1, 10):
                # Check if the position is within track bounds
                if index_rouleur + d >= len(tracé.cases):
                    break
                if tracé.cases[index_rouleur + d].pente == Pente.col:
                    if d <= 5:
                        max_rouleur = 5
                    else:
                        max_rouleur = d - 1

                    ér = [é for é in énergies_rouleur if é <= max_rouleur]
                    if len(ér) == 0:
                        ér = [min(énergies_rouleur)]
                    break
            rouleur = max(ér)

        énergies_sprinteur.remove(sprinteur)
        énergies_rouleur.remove(rouleur)

        self.défausse_sprinteur.extend(énergies_sprinteur)
        self.défausse_rouleur.extend(énergies_rouleur)

        return Paire(sprinteur, rouleur)
