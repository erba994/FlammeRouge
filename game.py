#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Track display and game logic for Flamme Rouge.

This module contains the core game mechanics including:
- Track visualization and ASCII art rendering
- Rider movement and positioning logic
- Race mechanics (aspiration, fatigue, etc.)
- Display mode management for different track views
"""

import collections
import logging

from models import Pente, Profil


class Tracé:
    """The race track with display and game logic capabilities."""
    
    def __init__(self, cases, départ, arrivée, lg_tour):
        """Initialize the race track.
        
        Args:
            cases (list): List of Case objects representing the track
            départ (int): Starting line position index
            arrivée (int): Finish line position index
            lg_tour (int): Length of one lap in cases
        """
        self.cases = cases
        self._départ = départ
        self._arrivée = arrivée
        self._lg_tour = lg_tour
        self.positions = dict()  # Maps Pion -> position index

    @property
    def départ(self):
        """Index of the first race case."""
        return self._départ

    @property
    def arrivée(self):
        """Index of the last race case."""
        return self._arrivée

    @property
    def lg_tour(self):
        """Number of cases in one lap."""
        return self._lg_tour

    def est_flamme(self, indice):
        """Check if a case is a flame rouge (important) position.
        
        Args:
            indice (int): Case index to check
            
        Returns:
            bool: True if this is a start, finish, or lap marker position
        """
        return (indice == self.départ or indice == self.arrivée
                or (indice - self.départ) % self.lg_tour == 0)

    def poser(self, pion, ligne):
        """Place a rider piece on the track at the given line.
        
        Args:
            pion (Pion): The rider piece to place
            ligne (int): Target position to place the rider
        """
        for i in reversed(range(ligne + 1)):
            if self.cases[i].poser(pion):
                self.positions[pion] = i
                break
        else:
            logging.error("Pas de place!")

    def retirer(self, pion):
        """Remove a rider piece from the track.
        
        Args:
            pion (Pion): The rider piece to remove
        """
        self.cases[self.positions[pion]].retirer(pion)
        del self.positions[pion]

    def afficher(self, début=None, garde=None, aspiration=list(), 
                mode='window', max_width=80, show_full=False):
        """Display the track with various modes.
        
        Args:
            début: Start position (for window mode)
            garde: End position (for window mode)  
            aspiration: List of aspiration positions
            mode: Display mode - 'window', 'full', 'wrapped', 'overview'
            max_width: Maximum terminal width for wrapped mode
            show_full: Legacy parameter for backward compatibility
        """
        if mode == 'full' or show_full:
            self._afficher_full_track(aspiration, max_width)
        elif mode == 'wrapped':
            self._afficher_wrapped_track(aspiration, max_width)
        elif mode == 'overview':
            self._afficher_overview_track(aspiration, max_width)
        else:  # mode == 'window' or default
            self._afficher_window_track(début, garde, aspiration)

    def _afficher_window_track(self, début=None, garde=None, aspiration=list()):
        """Original windowed display - maintains backward compatibility."""
        if début is None:
            début = min(self.positions.values(), default=0)
        if garde is None:
            garde = 1 + max(self.positions.values(), default=len(self.cases))

        # Ligne supérieure
        segments = [""]
        for i in range(début, garde):
            case = self.cases[i]
            if case.pente == Pente.plat:
                segments.append("~~~~")
            elif case.pente == Pente.col:
                segments.append("<<<<")
            else:  # case.pente == Pente.descente
                segments.append(">>>>")
        segments.append("")
        print("+".join(segments))

        # Côté gauche
        ligne = str()
        for i in range(début, garde):
            if self.est_flamme(i):
                ligne += "‖ "
            else:
                ligne += "| "
            if i in aspiration:
                ligne += "→→"
            else:
                pion = self.cases[i].gauche
                if pion is None:
                    ligne += "  "
                else:
                    ligne += str(pion)
            ligne += " "
        if self.est_flamme(garde):
            ligne += "‖"
        else:
            ligne += "|"
        print(ligne)

        # Ligne médiane
        ligne = str()
        for i in range(début, garde):
            ligne += "+----"
        ligne += "+"
        print(ligne)

        # Côté droit
        ligne = str()
        for i in range(début, garde):
            if self.est_flamme(i):
                ligne += "‖ "
            else:
                ligne += "| "
            if i in aspiration:
                ligne += "→→"
            else:
                pion = self.cases[i].droite
                if pion is None:
                    ligne += "  "
                else:
                    ligne += str(pion)
            ligne += " "
        if self.est_flamme(garde):
            ligne += "‖"
        else:
            ligne += "|"
        print(ligne)

        # Ligne inférieure
        segments = [""]
        for i in range(début, garde):
            case = self.cases[i]
            if case.pente == Pente.plat:
                segments.append("====")
            elif case.pente == Pente.col:
                segments.append("<<<<")
            else:  # case.pente == Pente.descente
                segments.append(">>>>")
        segments.append("")
        print("+".join(segments))

        # Numéro de case
        ligne = str()
        for i in range(début, garde):
            if self.est_flamme(i):
                ligne += "‖{: <4}".format(i - self.départ)
            else:
                ligne += "|{: <4}".format(i - self.départ)
        if self.est_flamme(garde):
            ligne += "‖"
        else:
            ligne += "|"
        print(ligne)

        # Changement de pente
        self._afficher_terrain_info(garde)

    def _afficher_full_track(self, aspiration=list(), max_width=80):
        """Display the complete track in a single view."""
        début = 0
        garde = len(self.cases)
        
        # Calculate if track fits in terminal width
        track_width = (garde - début) * 5 + 1  # 5 chars per case + final border
        
        if track_width <= max_width:
            # Track fits in single line
            self._afficher_window_track(début, garde, aspiration)
        else:
            # Track too wide, use wrapped mode
            self._afficher_wrapped_track(aspiration, max_width)

    def _afficher_wrapped_track(self, aspiration=list(), max_width=80):
        """Display track with line wrapping for long tracks."""
        début = 0
        garde = len(self.cases)
        
        # Calculate cases per line (accounting for borders)
        cases_per_line = (max_width - 1) // 5  # 5 chars per case
        if cases_per_line < 10:  # Minimum reasonable display
            cases_per_line = 10
            
        print(f"=== FULL TRACK DISPLAY ({garde - début} cases) ===")
        
        # Display track in segments
        for segment_start in range(début, garde, cases_per_line):
            segment_end = min(segment_start + cases_per_line, garde)
            
            print(f"\n--- Cases {segment_start - self.départ} to {segment_end - 1 - self.départ} ---")
            self._afficher_window_track(segment_start, segment_end, aspiration)

    def _afficher_overview_track(self, aspiration=list(), max_width=80):
        """Display compressed overview with detailed current section."""
        if not self.positions:
            # No riders, show full track
            self._afficher_full_track(aspiration, max_width)
            return
            
        # Find rider positions
        min_pos = min(self.positions.values())
        max_pos = max(self.positions.values())
        
        # Show detailed view around riders
        detail_start = max(0, min_pos - 5)
        detail_end = min(len(self.cases), max_pos + 10)
        
        print("=== RACE OVERVIEW ===")
        print(f"Full track: 0 to {len(self.cases) - 1 - self.départ} km")
        print(f"Riders between km {min_pos - self.départ} and {max_pos - self.départ}")
        print()
        print("=== DETAILED VIEW (Current Race Position) ===")
        self._afficher_window_track(detail_start, detail_end, aspiration)
        
        # Show compressed full track overview
        print("\n=== COMPRESSED TRACK OVERVIEW ===")
        self._afficher_compressed_overview()

    def _afficher_compressed_overview(self):
        """Show a compressed view of the entire track."""
        # Create a simplified track representation
        track_repr = []
        
        for i in range(len(self.cases)):
            if self.est_flamme(i):
                symbol = "F"  # Flame rouge
            elif self.cases[i].pente == Pente.col:
                symbol = "^"  # Climb
            elif self.cases[i].pente == Pente.descente:
                symbol = "v"  # Descent
            else:
                symbol = "-"  # Flat
                
            # Mark rider positions
            if any(pos == i for pos in self.positions.values()):
                symbol = "*"  # Riders here
                
            track_repr.append(symbol)
        
        # Display in chunks
        chunk_size = 70
        for i in range(0, len(track_repr), chunk_size):
            chunk = track_repr[i:i + chunk_size]
            km_start = i - self.départ
            km_end = min(i + chunk_size - 1, len(track_repr) - 1) - self.départ
            print(f"km {km_start:3d}-{km_end:3d}: {''.join(chunk)}")
        
        print("\nLegend: F=Flame Rouge, ^=Climb, v=Descent, -=Flat, *=Riders")

    def _afficher_terrain_info(self, garde):
        """Display terrain change information."""
        if garde >= len(self.cases):
            return  # No terrain info beyond track end
            
        for i in range(garde, len(self.cases)):
            ligne = None
            if i == self.arrivée:
                ligne = " Arrivée au km {}".format(i - self.départ)
            elif garde > 0 and garde <= len(self.cases) and i < len(self.cases) and self.cases[garde - 1].pente != self.cases[i].pente:
                ligne = " Prochain point d'étape au km {} : ".format(
                    i - self.départ)
                j = i + 1
                while (j < self.arrivée
                       and j < len(self.cases)
                       and self.cases[j].pente == self.cases[i].pente):
                    j += 1
                if self.cases[i].pente == Pente.col:
                    ligne += "ascension"
                elif self.cases[i].pente == Pente.plat:
                    ligne += "plaine"
                else:  # self.cases[i].pente == Pente.descente
                    ligne += "descente"
                ligne += " de {} km".format(j - i)

            if ligne is not None:
                print(ligne)
                break

    def déplacer(self, paires):
        """Apply rider movements from front to back to avoid conflicts.
        
        Args:
            paires (dict): Map of joueur -> Paire(sprinteur_energy, rouleur_energy)
        """
        for i in reversed(
                range(min(self.positions.values()),
                      1 + max(self.positions.values()))):
            case = self.cases[i]
            # Process right rider first
            pion = case.droite
            if pion is not None:
                paire = paires[pion.joueur]
                énergie = paire.rouleur
                if pion.profil == Profil.sprinteur:
                    énergie = paire.sprinteur
                self._déplacer_pion(pion, énergie)
            # Then process left rider
            pion = case.gauche
            if pion is not None:
                paire = paires[pion.joueur]
                énergie = paire.rouleur
                if pion.profil == Profil.sprinteur:
                    énergie = paire.sprinteur
                self._déplacer_pion(pion, énergie)

    def _déplacer_pion(self, pion, énergie):
        """Move a single rider piece according to game rules.
        
        Args:
            pion (Pion): The rider to move
            énergie (int): Energy points to spend on movement
        """
        # Find current position
        i = self.positions[pion]
        self.retirer(pion)

        # Cannot go beyond track end
        énergie = min(énergie, len(self.cases) - i - 1)

        # Apply movement rules
        if self.cases[i].pente == Pente.descente:
            énergie = max(5, énergie)

        for j in range(énergie + 1):
            if self.cases[i + j].pente == Pente.col:
                énergie = min(énergie, max(5, j - 1))

        # Execute movement
        self.poser(pion, i + énergie)

    def aspirer(self, joueurs):
        """Apply slipstream mechanics to pull riders forward.
        
        Args:
            joueurs (list): List of all players for display purposes
        """
        # Determine slipstream cases
        cases_aspiration = list()
        for i in range(
                min(self.positions.values()) + 1,
                max(self.positions.values())):
            if (not self.cases[i - 1].est_vide()
                    and not self.cases[i - 1].pente == Pente.col
                    and self.cases[i].est_vide()
                    and not self.cases[i + 1].est_vide()
                    and not self.cases[i + 1].pente == Pente.col):
                cases_aspiration.append(i)

        # Display slipstream effect
        if len(cases_aspiration) != 0:
            for joueur in joueurs:
                joueur.client.afficher(self, aspiration=cases_aspiration)

        # Apply slipstream movement
        for i in cases_aspiration:
            j = i - 1
            while not (self.cases[j].est_vide()
                       or self.cases[j].pente == Pente.col):
                case = self.cases[j]
                pion = case.droite
                self.retirer(pion)
                self.poser(pion, j + 1)
                pion = case.gauche
                if pion is not None:
                    self.retirer(pion)
                    self.poser(pion, j + 1)
                j -= 1

    def fatiguer(self):
        """Add fatigue to all riders exposed to headwind.
        
        Returns:
            dict: Map of couleur -> list of fatigued riders
        """
        fatigués = collections.defaultdict(list)

        for i in range(min(self.positions.values()),
                       1 + max(self.positions.values())):
            case = self.cases[i]
            if (not case.est_vide() and i < self.arrivée
                    and self.cases[i + 1].est_vide()):
                pion = case.droite
                if pion.profil == Profil.sprinteur:
                    pion.joueur.défausse_sprinteur.append(2)
                else:
                    pion.joueur.défausse_rouleur.append(2)
                fatigués[pion.joueur.couleur].append(pion)

                pion = case.gauche
                if pion is not None:
                    if pion.profil == Profil.sprinteur:
                        pion.joueur.défausse_sprinteur.append(2)
                    else:
                        pion.joueur.défausse_rouleur.append(2)
                    fatigués[pion.joueur.couleur].append(pion)

        return fatigués

    def afficher_fatigue(self, fatigués, couleur_joueur):
        """Display fatigue assignment information.
        
        Args:
            fatigués (dict): Map of color -> list of fatigued riders
            couleur_joueur (str): Current player's color for highlighting
        """
        # Handle both string and enum colors for sorting
        def get_color_name(c):
            return c.name if hasattr(c, 'name') else str(c)
        
        print("\n=== FATIGUE ASSIGNMENT ===")

        for couleur in sorted(fatigués, key=get_color_name):
            color_name = couleur.name if hasattr(couleur, 'name') else str(couleur)
            ligne = "Équipe {}e : fatigue ".format(color_name)
            coureurs = sorted(fatigués[couleur], key=str)
            ligne += " et ".join(
                ["du {}".format(x.profil.name) for x in coureurs])
            if color_name == couleur_joueur:
                ligne += " <---"
            print(ligne)
        
        print("\n")

    def ordre(self):
        """Get the current race order of teams.
        
        Returns:
            list: Team colors in order from first to last place
        """
        couleurs = list()
        for i in reversed(
                range(min(self.positions.values()),
                      max(self.positions.values()) + 1)):
            case = self.cases[i]
            pion = case.droite
            if pion is not None and pion.joueur.couleur not in couleurs:
                couleurs.append(pion.joueur.couleur)
            pion = case.gauche
            if pion is not None and pion.joueur.couleur not in couleurs:
                couleurs.append(pion.joueur.couleur)

        return couleurs
