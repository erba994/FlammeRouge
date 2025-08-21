#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Game models and data structures for Flamme Rouge.

This module contains the core data classes that represent game entities:
- Terrain types and track components
- Player pieces and game positions
- Game state enumerations and constants
"""

import collections
import enum


class Couleur(enum.Enum):
    """Player team colors."""
    bleu = 1
    noir = 2
    gris = 3
    vert = 4


class Pente(enum.Enum):
    """Track slope types perceived in the direction of movement."""
    plat = 0        # Flat terrain
    col = 1         # Climb/ascent
    descente = 2    # Descent


class Profil(enum.Enum):
    """Cyclist profile types."""
    sprinteur = 1   # Sprinter
    rouleur = 2     # Rouleur (all-rounder)


class Case:
    """A single track segment that can hold up to two riders."""
    
    def __init__(self, pente):
        """Initialize a track case with the given slope type.
        
        Args:
            pente (Pente): The slope type of this track segment
        """
        self.droite = None  # Right position rider
        self.gauche = None  # Left position rider  
        self.pente = pente  # Terrain slope type

    def est_vide(self):
        """Check if the track case is empty (no riders).
        
        Returns:
            bool: True if both positions are empty
        """
        return (self.droite is None and self.gauche is None)

    def poser(self, pion):
        """Place a rider piece on this track case.
        
        Args:
            pion (Pion): The rider piece to place
            
        Returns:
            bool: True if the piece was successfully placed, False if case is full
        """
        if self.droite is None:
            self.droite = pion
            return True
        elif self.gauche is None:
            self.gauche = pion
            return True
        else:
            return False

    def retirer(self, pion):
        """Remove a rider piece from this track case.
        
        Args:
            pion (Pion): The rider piece to remove
        """
        if self.droite == pion:
            self.droite = None
        else:
            self.gauche = None


class Pion(collections.namedtuple("Pion", ["profil", "joueur"])):
    """A rider piece representing a cyclist on the track.
    
    Attributes:
        profil (Profil): The cyclist type (sprinter or rouleur)
        joueur (Joueur): The player who owns this cyclist
    """
    
    def __str__(self):
        """Generate display representation of the rider piece.
        
        Returns:
            str: Two-character code (profile initial + color initial)
        """
        retour = self.profil.name[0].upper()
        # Handle string colors properly
        color_name = self.joueur.couleur if isinstance(self.joueur.couleur, str) else self.joueur.couleur.name
        retour += color_name[0].lower()
        return retour


# Named tuple for player move pairs
Paire = collections.namedtuple("Paire", ["sprinteur", "rouleur"])
