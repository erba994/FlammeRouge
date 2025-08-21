#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Networking and client interfaces for Flamme Rouge.

This module contains the client-server communication infrastructure:
- Base client interface for display and interaction
- Console client for local terminal play
- Network clients for multiplayer functionality
- Protocol handling for game state synchronization
"""

import pickle
import socket

from models import Paire


class ClientServeur:
    """Base networking functionality for client-server communication."""
    
    def send(self, socket_tx, msg):
        """Send a message with length prefix over a socket.
        
        Args:
            socket_tx: The socket to send through
            msg (bytes): The message to send
            
        Returns:
            socket: The socket for chaining
        """
        socket_tx.send('{}:'.format(len(msg)).encode('utf-8'))
        socket_tx.send(msg)
        return socket_tx

    def recv(self, socket_rx):
        """Receive a length-prefixed message from a socket.
        
        Args:
            socket_rx: The socket to receive from
            
        Returns:
            bytes: The received message
        """
        longueur = 0
        while True:
            message = socket_rx.recv(1).decode('utf-8')
            if message == ':' or message < '0' or message > '9':
                break
            longueur = longueur * 10 + int(message)

        fragments = []
        while longueur > 0:
            fragment = socket_rx.recv(longueur)
            fragments.append(fragment)
            longueur -= len(fragment)

        return b''.join(fragments)


class Client:
    """Abstract base class for game clients."""
    
    def __init__(self):
        """Initialize client with default attributes."""
        self._couleur = None
    
    def __getstate__(self):
        """Prevent pickling issues during serialization."""
        return None

    def afficher(self, tracé, début=None, garde=None, aspiration=list()):
        """Display the race track.
        
        Args:
            tracé: The race track to display
            début: Start position for windowed view
            garde: End position for windowed view
            aspiration: List of slipstream positions
        """
        raise NotImplementedError

    def afficher_fatigue(self, tracé, fatigués):
        """Display fatigue assignment.
        
        Args:
            tracé: The race track
            fatigués: Dictionary of fatigued riders by team
        """
        raise NotImplementedError

    def demander_positions(self, tracé, libres):
        """Request starting positions from player.
        
        Args:
            tracé: The race track
            libres: List of available starting positions
            
        Returns:
            Paire: Selected positions for sprinter and rouleur
        """
        raise NotImplementedError

    def demander_jeu(self, énergies_sprinteur, énergies_rouleur):
        """Request energy card selection from player.
        
        Args:
            énergies_sprinteur: Available sprinter energy cards
            énergies_rouleur: Available rouleur energy cards
            
        Returns:
            Paire: Selected energy cards for both riders
        """
        raise NotImplementedError

    def ordre(self, couleurs):
        """Display race standings.
        
        Args:
            couleurs: Team colors in race order
        """
        raise NotImplementedError

    def attente(self, couleurs):
        """Display waiting message for other players.
        
        Args:
            couleurs: Colors of players still making decisions
        """
        raise NotImplementedError

    def couleur(self, couleur):
        """Set the player's team color.
        
        Args:
            couleur: The team color (enum or string)
        """
        # Accept both enum and string, but use string directly
        if hasattr(couleur, 'name'):
            self._couleur = couleur.name
        else:
            self._couleur = str(couleur)

    @property
    def couleur_str(self):
        """Get the color as a string."""
        return self._couleur


class ClientNul(Client):
    """Null client that does nothing - used for headless AI players."""
    
    def __init__(self):
        super().__init__()
    
    def afficher(self, tracé, début=None, garde=None, aspiration=list()):
        """No-op display method."""
        pass

    def afficher_fatigue(self, tracé, fatigués):
        """No-op fatigue display method."""
        pass

    def demander_positions(self, tracé, libres):
        """No-op position selection method."""
        pass

    def demander_jeu(self, énergies_sprinteur, énergies_rouleur):
        """No-op energy card selection method."""
        pass

    def ordre(self, couleurs):
        """No-op standings display method."""
        pass

    def attente(self, couleurs):
        """No-op waiting message method."""
        pass


class ServeurConsole(Client, ClientServeur):
    """Server-side console for networked multiplayer games."""
    
    def __init__(self):
        """Initialize the network server."""
        serveur = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        serveur.bind((socket.gethostname(), 0))
        print(serveur.getsockname()[1])
        serveur.listen(1)
        self.socket = serveur.accept()[0]

    def afficher(self, tracé, début=None, garde=None, aspiration=list()):
        """Send display command to network client."""
        message = pickle.dumps({
            "commande": "afficher",
            "tracé": tracé,
            "début": début,
            "garde": garde,
            "aspiration": aspiration
        })
        self.send(self.socket, message)

    def afficher_fatigue(self, tracé, fatigués):
        """Send fatigue display command to network client."""
        message = pickle.dumps({
            "commande": "afficher_fatigue",
            "tracé": tracé,
            "fatigués": fatigués
        })
        self.send(self.socket, message)

    def demander_positions(self, tracé, libres):
        """Request starting positions from network client."""
        message = pickle.dumps({
            "commande": "demander_positions",
            "tracé": tracé,
            "libres": libres
        })
        while True:
            self.send(self.socket, message)
            try:
                réponse = self.recv(self.socket)
                positions = pickle.loads(réponse)
                libres_temp = list(libres)
                sprinteur = positions.sprinteur
                rouleur = positions.rouleur
                libres_temp.remove(sprinteur)
                libres_temp.remove(rouleur)
                break
            except ValueError:
                pass

        return Paire(sprinteur, rouleur)

    def demander_jeu(self, énergies_sprinteur, énergies_rouleur):
        """Request energy card selection from network client."""
        message = pickle.dumps({
            "commande": "demander_jeu",
            "énergies_sprinteur": énergies_sprinteur,
            "énergies_rouleur": énergies_rouleur
        })
        while True:
            self.send(self.socket, message)
            try:
                réponse = self.recv(self.socket)
                énergies = pickle.loads(réponse)
                sprinteur = énergies.sprinteur
                rouleur = énergies.rouleur
                énergies_sprinteur_temp = list(énergies_sprinteur)
                énergies_sprinteur_temp.remove(sprinteur)
                énergies_rouleur_temp = list(énergies_rouleur)
                énergies_rouleur_temp.remove(rouleur)
                break
            except ValueError:
                pass

        return Paire(sprinteur, rouleur)

    def ordre(self, couleurs):
        """Send race standings to network client."""
        message = pickle.dumps({"commande": "ordre", "couleurs": couleurs})
        self.send(self.socket, message)

    def attente(self, couleurs):
        """Send waiting message to network client."""
        message = pickle.dumps({"commande": "attente", "couleurs": couleurs})
        self.send(self.socket, message)

    def couleur(self, couleur):
        """Send team color assignment to network client."""
        message = pickle.dumps({"commande": "couleur", "couleur": couleur})
        self.send(self.socket, message)


class Console(Client):
    """Local console client for terminal-based gameplay."""
    
    def __init__(self, display_mode='window'):
        """Initialize console with specified display mode.
        
        Args:
            display_mode (str): Track display mode ('window', 'full', 'wrapped', 'overview')
        """
        super().__init__()
        self.display_mode = display_mode
        
    def afficher(self, tracé, début=None, garde=None, aspiration=list()):
        """Display the race track using the configured display mode."""
        if début is None:
            print("\n")

        # Use the configured display mode
        tracé.afficher(début, garde, aspiration, mode=self.display_mode)

    def set_display_mode(self, mode):
        """Set the display mode.
        
        Args:
            mode (str): Display mode ('window', 'full', 'wrapped', 'overview')
        """
        if mode in ['window', 'full', 'wrapped', 'overview']:
            self.display_mode = mode
            print(f"Display mode set to: {mode}")
        else:
            print(f"Invalid display mode: {mode}. Valid modes: window, full, wrapped, overview")

    def afficher_fatigue(self, tracé, fatigués):
        """Display fatigue assignment with highlighting for current player."""
        tracé.afficher_fatigue(fatigués, self._couleur)

    def demander_positions(self, tracé, libres):
        """Interactive starting position selection."""
        while True:
            try:
                sprinteur = tracé.départ + int(
                    input("Position du sprinteur {} ? ".format(self._couleur)))
                if sprinteur in libres:
                    libres.remove(sprinteur)
                    break
            except ValueError:
                pass

        while True:
            try:
                rouleur = tracé.départ + int(
                    input("Position du rouleur {} ? ".format(self._couleur)))
                if rouleur in libres:
                    libres.remove(rouleur)
                    break
            except ValueError:
                pass

        return Paire(sprinteur, rouleur)

    def demander_jeu(self, énergies_sprinteur, énergies_rouleur):
        """Interactive energy card selection."""
        print("Choix du sprinteur : {}".format(", ".join(
            map(str, énergies_sprinteur))))
        print("Choix du rouleur : {}".format(", ".join(
            map(str, énergies_rouleur))))

        while True:
            try:
                sprinteur = int(
                    input("Énergie du sprinteur {} ? ".format(self._couleur)))
                énergies_sprinteur.remove(sprinteur)
                break
            except ValueError:
                pass

        while True:
            try:
                rouleur = int(
                    input("Énergie du rouleur {} ? ".format(self._couleur)))
                énergies_rouleur.remove(rouleur)
                break
            except ValueError:
                pass

        return Paire(sprinteur, rouleur)

    def ordre(self, couleurs):
        """Display race standings with highlighting for current player."""
        for i in range(len(couleurs)):
            # Handle both enum and string colors
            color_name = couleurs[i].name if hasattr(couleurs[i], 'name') else str(couleurs[i])
            ligne = "N°{} : équipe {}e".format(i + 1, color_name)
            if color_name == self._couleur:
                ligne += " <---"
            print(ligne)

    def attente(self, couleurs):
        """Display waiting message for other players."""
        print("Attente joueur{} : {}".format("s" if len(couleurs) > 1 else "",
                                             ", ".join(couleurs)))

    def couleur(self, couleur):
        """Set and display the player's team color."""
        # Accept both enum and string, but use string directly
        if hasattr(couleur, 'name'):
            self._couleur = couleur.name
            print("Vous êtes le joueur {}".format(couleur.name))
        else:
            self._couleur = str(couleur)
            print("Vous êtes le joueur {}".format(couleur))


class ClientConsole(Console, ClientServeur):
    """Network client that connects to a remote game server."""
    
    def __init__(self, adresse, port):
        """Initialize network client connection.
        
        Args:
            adresse (str): Server address to connect to
            port (int): Server port to connect to
        """
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.connect((adresse, port))

    def jouer(self):
        """Main client loop for processing server commands."""
        while True:
            try:
                message = self.recv(self.socket)
                msg = pickle.loads(message)
                if msg['commande'] == "afficher":
                    Console.afficher(self, msg['tracé'], msg['début'],
                                     msg['garde'], msg['aspiration'])
                elif msg['commande'] == "afficher_fatigue":
                    Console.afficher_fatigue(self, msg['tracé'],
                                             msg['fatigués'])
                elif msg['commande'] == "demander_positions":
                    positions = Console.demander_positions(
                        self, msg['tracé'], msg['libres'])
                    réponse = pickle.dumps(positions)
                    self.socket = self.send(self.socket, réponse)
                elif msg['commande'] == "demander_jeu":
                    énergies = Console.demander_jeu(self,
                                                    msg['énergies_sprinteur'],
                                                    msg['énergies_rouleur'])
                    réponse = pickle.dumps(énergies)
                    self.socket = self.send(self.socket, réponse)
                elif msg['commande'] == "ordre":
                    Console.ordre(self, msg['couleurs'])
                    break
                elif msg['commande'] == "attente":
                    Console.attente(self, msg['couleurs'])
                elif msg['commande'] == "couleur":
                    Console.couleur(self, msg['couleur'])
            except ValueError as err:
                print(err)
                pass

        self.socket.close()


def client_console(adresse, port):
    """Create and run a network client console.
    
    Args:
        adresse (str): Server address
        port (int): Server port
    """
    client = ClientConsole(adresse, port)
    client.jouer()
