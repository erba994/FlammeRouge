#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Copyright ou © ou Copr. Guillaume Lemaître (2016, 2020)
#
#   guillaume.lemaitre@gmail.com
#
# Ce logiciel est un programme informatique permettant de jouer seul au jeu de
# plateau "Flamme rouge" avec un visuel bien infect.
#
# Ce logiciel est régi par la licence CeCILL soumise au droit français et
# respectant les principes de diffusion des logiciels libres. Vous pouvez
# utiliser, modifier et/ou redistribuer ce programme sous les conditions de la
# licence CeCILL telle que diffusée par le CEA, le CNRS et l'INRIA sur le site
# "http://www.cecill.info".
#
# En contrepartie de l'accessibilité au code source et des droits de copie, de
# modification et de redistribution accordés par cette licence, il n'est
# offert aux utilisateurs qu'une garantie limitée. Pour les mêmes raisons,
# seule une responsabilité restreinte pèse sur l'auteur du programme, le
# titulaire des droits patrimoniaux et les concédants successifs.
#
# À cet égard, l'attention de l'utilisateur est attirée sur les risques
# associés au chargement, à l'utilisation, à la modification et/ou au
# développement et à la reproduction du logiciel par l'utilisateur étant donné
# sa spécificité de logiciel libre, qui peut le rendre complexe à manipuler et
# qui le réserve donc à des développeurs et des professionnels avertis
# possédant des connaissances informatiques approfondies. Les utilisateurs
# sont donc invités à charger et tester l'adéquation du logiciel à leurs
# besoins dans des conditions permettant d'assurer la sécurité de leurs
# systèmes et ou de leurs données et, plus généralement, à l'utiliser et
# l'exploiter dans les mêmes conditions de sécurité.
#
# Le fait que vous puissiez accéder à cet en-tête signifie que vous avez pris
# connaissance de la licence CeCILL, et que vous en avez accepté les termes.
"""Implémentation du jeu "Flamme rouge" pour un joueur
"""

import collections
import enum
import json
import logging
import os.path
import pickle
import random
import yaml
import socket
import sys
import threading
import time


def choisir_course(chemin):
    # Lecture du fichier
    parcours = None
    with open(chemin, "rt", encoding="utf-8") as entrée:
        parcours = json.load(entrée)

    # Vérification
    for nom_case, case in parcours["cases"].items():
        if not ("angle" in case and "pente" in case):
            logging.error(f"Case {nom_case} incohérente")

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

    # Choix de la course par le joueur
    noms = sorted(parcours["courses"])
    for i, nom_course in enumerate(noms):
        print("{}) {}".format(i + 1, nom_course))
    while True:
        try:
            i = int(input("Choix du parcours ? ")) - 1
            if 0 <= i < len(noms):
                nom_course = noms[i]
                break
        except ValueError:
            pass

    # Construction de la course choisie
    cases = list()
    départ = None
    arrivée = None
    course = parcours["courses"][nom_course]
    nb_tours = course["tours"]
    tronçons = course["tracé"]
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
    if nb_tours == 1:
        lg_circuit = arrivée - départ
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

    tracé = Tracé(cases, départ, arrivée, lg_circuit)
    return tracé, nb_tours


class Couleur(enum.Enum):

    bleu = 1
    noir = 2
    gris = 3
    vert = 4


Paire = collections.namedtuple("Paire", ["sprinteur", "rouleur"])


class ClientServeur:
    def send(self, socket_tx, msg):
        socket_tx.send('{}:'.format(len(msg)).encode('utf-8'))
        socket_tx.send(msg)
        return socket_tx

    def recv(self, socket_rx):
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
    def __getstate__(self):
        None

    def afficher(self, tracé, début=None, garde=None, aspiration=list()):
        raise NotImplementedError

    def afficher_fatigue(self, tracé, fatigués):
        raise NotImplementedError

    def demander_positions(self, tracé, libres):
        raise NotImplementedError

    def demander_jeu(self, choix_sprinteur, choix_rouleur):
        raise NotImplementedError

    def ordre(self, couleurs):
        raise NotImplementedError

    def attente(self, couleurs):
        raise NotImplementedError

    def couleur(self, couleur):
        # Accept both enum and string, but use string directly
        if hasattr(couleur, 'name'):
            self.couleur = couleur.name
        else:
            self.couleur = str(couleur)


class ClientNul(Client):
    def afficher(self, tracé, début=None, garde=None, aspiration=list()):
        pass

    def afficher_fatigue(self, tracé, fatigués):
        pass

    def demander_positions(self, tracé, libres):
        pass

    def demander_jeu(self, choix_sprinteur, choix_rouleur):
        pass

    def ordre(self, couleurs):
        pass

    def attente(self, couleurs):
        pass


class ServeurConsole(Client, ClientServeur):
    def __init__(self):
        serveur = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        serveur.bind((socket.gethostname(), 0))
        print(serveur.getsockname()[1])
        serveur.listen(1)
        self.socket = serveur.accept()[0]

    def afficher(self, tracé, début=None, garde=None, aspiration=list()):
        message = pickle.dumps({
            "commande": "afficher",
            "tracé": tracé,
            "début": début,
            "garde": garde,
            "aspiration": aspiration
        })
        self.send(self.socket, message)

    def afficher_fatigue(self, tracé, fatigués):
        message = pickle.dumps({
            "commande": "afficher_fatigue",
            "tracé": tracé,
            "fatigués": fatigués
        })
        self.send(self.socket, message)

    def demander_positions(self, tracé, libres):
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

        # message = pickle.dumps({"commande": "position_ok"})
        # self.send(self.socket, message)

        return Paire(sprinteur, rouleur)

    def demander_jeu(self, énergies_sprinteur, énergies_rouleur):
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

        # message = pickle.dumps({"commande": "jeu_ok"})
        # self.send(self.socket, message)

        return Paire(sprinteur, rouleur)

    def ordre(self, couleurs):
        message = pickle.dumps({"commande": "ordre", "couleurs": couleurs})
        self.send(self.socket, message)

    def attente(self, couleurs):
        message = pickle.dumps({"commande": "attente", "couleurs": couleurs})
        self.send(self.socket, message)

    def couleur(self, couleur):
        message = pickle.dumps({"commande": "couleur", "couleur": couleur})
        self.send(self.socket, message)


class Console(Client):
    def __init__(self, display_mode='window'):
        self.display_mode = display_mode
        
    def afficher(self, tracé, début=None, garde=None, aspiration=list()):
        if début is None:
            print("\n")

        # Use the configured display mode
        tracé.afficher(début, garde, aspiration, mode=self.display_mode)

    def set_display_mode(self, mode):
        """Set the display mode: 'window', 'full', 'wrapped', 'overview'"""
        if mode in ['window', 'full', 'wrapped', 'overview']:
            self.display_mode = mode
            print(f"Display mode set to: {mode}")
        else:
            print(f"Invalid display mode: {mode}. Valid modes: window, full, wrapped, overview")

    def afficher_fatigue(self, tracé, fatigués):
        tracé.afficher_fatigue(fatigués, self.couleur)

    def demander_positions(self, tracé, libres):
        while True:
            try:
                sprinteur = tracé.départ + int(
                    input("Position du sprinteur {} ? ".format(self.couleur)))
                if sprinteur in libres:
                    libres.remove(sprinteur)
                    break
            except ValueError:
                pass

        while True:
            try:
                rouleur = tracé.départ + int(
                    input("Position du rouleur {} ? ".format(self.couleur)))
                if rouleur in libres:
                    libres.remove(rouleur)
                    break
            except ValueError:
                pass

        return Paire(sprinteur, rouleur)

    def demander_jeu(self, énergies_sprinteur, énergies_rouleur):
        print("Choix du sprinteur : {}".format(", ".join(
            map(str, énergies_sprinteur))))
        print("Choix du rouleur : {}".format(", ".join(
            map(str, énergies_rouleur))))

        while True:
            try:
                sprinteur = int(
                    input("Énergie du sprinteur {} ? ".format(self.couleur)))
                énergies_sprinteur.remove(sprinteur)
                break
            except ValueError:
                pass

        while True:
            try:
                rouleur = int(
                    input("Énergie du rouleur {} ? ".format(self.couleur)))
                énergies_rouleur.remove(rouleur)
                break
            except ValueError:
                pass

        return Paire(sprinteur, rouleur)

    def ordre(self, couleurs):
        for i in range(len(couleurs)):
            # Handle both enum and string colors
            color_name = couleurs[i].name if hasattr(couleurs[i], 'name') else str(couleurs[i])
            ligne = "N°{} : équipe {}e".format(i + 1, color_name)
            if color_name == self.couleur:
                ligne += " <---"
            print(ligne)

    def attente(self, couleurs):
        print("Attente joueur{} : {}".format("s" if len(couleurs) > 1 else "",
                                             ", ".join(couleurs)))

    def couleur(self, couleur):
        # Accept both enum and string, but use string directly
        if hasattr(couleur, 'name'):
            self.couleur = couleur.name
            print("Vous êtes le joueur {}".format(couleur.name))
        else:
            self.couleur = str(couleur)
            print("Vous êtes le joueur {}".format(couleur))


class ClientConsole(Console, ClientServeur):
    def __init__(self, adresse, port):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.connect((adresse, port))

    def jouer(self):
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


class Joueur:
    def __init__(self, couleur, team_yaml_path, nb_tours):
        # Load team configuration from YAML file
        with open(team_yaml_path, 'r') as f:
            team_cfg = yaml.safe_load(f)
        self.couleur = couleur
        self.client = ClientNul()
        self.sprinteur = nb_tours * team_cfg.get('sprinteur', [])
        self.rouleur = nb_tours * team_cfg.get('rouleur', [])
        self.défausse_sprinteur = []
        self.défausse_rouleur = []
        random.shuffle(self.sprinteur)
        random.shuffle(self.rouleur)

    def placer(self, tracé):
        """Fournit une paire de lignes pour le placement sur la ligne de
        départ.
        """
        raise NotImplementedError

    def jouer(self, tracé):
        """Fournit une paire de déplacements pour ses coureurs
        """
        raise NotImplementedError

    def _piocher(self, tas, défausse):
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
    def __init__(self, couleur, team_yaml_path, nb_tours, client):
        super().__init__(couleur, team_yaml_path, nb_tours)
        self.client = client

    def placer(self, tracé):
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
        self.client.afficher(tracé)
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
    """Robot qui joue au pif
    """

    def __init__(self, couleur, team_yaml_path, nb_tours):
        super().__init__(couleur, team_yaml_path, nb_tours)

    def placer(self, tracé):
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
    def __init__(self, couleur, team_yaml_path, nb_tours):
        super().__init__(couleur, team_yaml_path, nb_tours)

    def jouer(self, tracé):
        énergies_sprinteur = self._piocher(self.sprinteur,
                                           self.défausse_sprinteur)
        énergies_rouleur = self._piocher(self.rouleur, self.défausse_rouleur)

        # On a beau jouer au pif, on évite de trop fatiguer
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
    """Robot qui joue tout ce qu'il a de plus fort
    """

    def __init__(self, couleur, team_yaml_path, nb_tours):
        super().__init__(couleur, team_yaml_path, nb_tours)

    def placer(self, tracé):
        return Paire(tracé.départ - 1, tracé.départ - 1)

    def jouer(self, tracé):
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
    """Robot qui joue tout ce qu'il a de plus fort, sans effort inutile
    """

    def __init__(self, couleur, team_yaml_path, nb_tours):
        super().__init__(couleur, team_yaml_path, nb_tours)

    def placer(self, tracé):
        return Paire(tracé.départ - 1, tracé.départ - 1)

    def jouer(self, tracé):
        énergies_sprinteur = self._piocher(self.sprinteur,
                                           self.défausse_sprinteur)
        énergies_rouleur = self._piocher(self.rouleur, self.défausse_rouleur)

        # On a beau être un bourrin, on évite de trop fatiguer
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


class Pente(enum.Enum):
    """Pente perçue dans le sens de la marche
    """

    plat = 0
    col = 1
    descente = 2


class Case:
    def __init__(self, pente):
        self.droite = None
        self.gauche = None
        self.pente = pente

    def est_vide(self):
        return (self.droite is None and self.gauche is None)

    def poser(self, pion):
        """Renvoit vrai ssi le pion a bien pu être posé sur la case
        """
        retour = True
        if self.droite is None:
            self.droite = pion
        elif self.gauche is None:
            self.gauche = pion
        else:
            retour = False
        return retour

    def retirer(self, pion):
        if self.droite == pion:
            self.droite = None
        else:
            self.gauche = None


class Profil(enum.Enum):

    sprinteur = 1
    rouleur = 2


class Pion(collections.namedtuple("Pion", ["profil", "joueur"])):
    def __str__(self):
        retour = self.profil.name[0].upper()
        # Handle string colors properly
        color_name = self.joueur.couleur if isinstance(self.joueur.couleur, str) else self.joueur.couleur.name
        retour += color_name[0].lower()

        return retour


class Tracé:
    def __init__(self, cases, départ, arrivée, lg_tour):
        self.cases = cases
        self._départ = départ
        self._arrivée = arrivée
        self._lg_tour = lg_tour

        self.positions = dict()

    @property
    def départ(self):
        """Indice de la première case de course
        """
        return self._départ

    @property
    def arrivée(self):
        """Indice de la dernière case de course
        """
        return self._arrivée

    @property
    def lg_tour(self):
        """Nombre de cases dans un tour
        """
        return self._lg_tour

    def est_flamme(self, indice):
        retour = (indice == self.départ or indice == self.arrivée
                  or (indice - self.départ) % self.lg_tour == 0)
        return retour

    def poser(self, pion, ligne):
        """Placement des pions sur la ligne de départ
        """
        for i in reversed(range(ligne + 1)):
            if self.cases[i].poser(pion):
                self.positions[pion] = i
                break
        else:
            logging.error("Pas de place!")

    def retirer(self, pion):
        self.cases[self.positions[pion]].retirer(pion)
        del self.positions[pion]

    def afficher(self, début=None, garde=None, aspiration=list(), 
                mode='window', max_width=80, show_full=False):
        """Display the track with various modes
        
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
        """Original windowed display - maintains backward compatibility"""
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
        """Display the complete track in a single view"""
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
        """Display track with line wrapping for long tracks"""
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
        """Display compressed overview with detailed current section"""
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
        """Show a compressed view of the entire track"""
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
        """Display terrain change information (extracted from original method)"""
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
        """Applique, du coureur en tête à la voiture-balai, les déplacements
        """
        for i in reversed(
                range(min(self.positions.values()),
                      1 + max(self.positions.values()))):
            case = self.cases[i]
            # Le pion droit d'abord
            pion = case.droite
            if pion is not None:
                paire = paires[pion.joueur]
                énergie = paire.rouleur
                if pion.profil == Profil.sprinteur:
                    énergie = paire.sprinteur
                self._déplacer_pion(pion, énergie)
            # ...puis le pion gauche
            pion = case.gauche
            if pion is not None:
                paire = paires[pion.joueur]
                énergie = paire.rouleur
                if pion.profil == Profil.sprinteur:
                    énergie = paire.sprinteur
                self._déplacer_pion(pion, énergie)

    def _déplacer_pion(self, pion, énergie):
        # Localisation du coureur
        i = self.positions[pion]
        self.retirer(pion)

        # On ne peut pas sortir du plateau
        énergie = min(énergie, len(self.cases) - i - 1)

        # Application des règles de déplacement
        if self.cases[i].pente == Pente.descente:
            énergie = max(5, énergie)

        for j in range(énergie + 1):
            if self.cases[i + j].pente == Pente.col:
                énergie = min(énergie, max(5, j - 1))

        # Déplacement effectif
        self.poser(pion, i + énergie)

    def aspirer(self, joueurs):
        """Applique l'algorithme d'aspiration
        """
        # Détermination des cases d'aspiration
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

        # Affichage
        if len(cases_aspiration) != 0:
            for joueur in joueurs:
                joueur.client.afficher(self, aspiration=cases_aspiration)

        # Application de l'aspiration
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
        """Ajoute de la fatigue à tous les coureurs face au vent
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
        # Handle both string and enum colors for sorting
        def get_color_name(c):
            return c.name if hasattr(c, 'name') else str(c)
        
        for couleur in sorted(fatigués, key=get_color_name):
            color_name = couleur.name if hasattr(couleur, 'name') else str(couleur)
            ligne = "Équipe {}e : fatigue ".format(color_name)
            coureurs = sorted(fatigués[couleur], key=str)
            ligne += " et ".join(
                ["du {}".format(x.profil.name) for x in coureurs])
            if color_name == couleur_joueur:
                ligne += " <---"
            print(ligne)

    def ordre(self):
        """Affiche l'ordre des équipes dans la course
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


def principal(nb_humains):
    tracé, nb_tours = choisir_course(
        os.path.join(os.path.dirname(sys.argv[0]), "courses.json"))

    import yaml
    config_path = os.path.join(os.path.dirname(sys.argv[0]), "game_config.yaml")
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)
    joueurs = []
    robot_classes = [Robot, Robourrin, Robomou, Rofinot]
    for team in config.get("teams", []):
        color = team.get("color", "unknown")
        yaml_path = team.get("yaml")
        team_type = team.get("type", "robot")
        if team_type == "human":
            joueurs.append(Humain(color, yaml_path, nb_tours, Console()))
        else:
            robot_class = random.choice(robot_classes)
            joueurs.append(robot_class(color, yaml_path, nb_tours))
    for joueur in joueurs:
        joueur.client.couleur(joueur.couleur)

    # Placement initial
    joueurs[0].client.afficher(tracé, 0, tracé.départ)
    for joueur in joueurs:
        for joueur_en_attente in joueurs:
            if joueur_en_attente is not joueur:
                # Handle string colors properly
                color_name = joueur.couleur if isinstance(joueur.couleur, str) else joueur.couleur.name
                joueur_en_attente.client.attente(list([color_name]))
        paire = joueur.placer(tracé)
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
        for joueur_en_attente in joueurs:
            joueur_en_attente.client.afficher(tracé, 0, tracé.départ)

    # Course !
    fin_de_partie = False
    while not fin_de_partie:

        # Phase énergie
        paires = dict()
        tâches = dict()

        for joueur in joueurs:
            if (joueur not in paires and
                    (joueur not in tâches or not tâches[joueur].is_alive())):
                tâches[joueur] = threading.Thread(
                    target=lambda t, j, p: p.update([(j, j.jouer(t))]),
                    args=(tracé, joueur, paires))
                tâches[joueur].start()

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
                if len([
                        c for c in attendre_couleurs_precedentes
                        if c not in attendre_couleurs
                ]):
                    for joueur in paires.keys():
                        joueur.client.attente(attendre_couleurs)
                    attendre_couleurs_precedentes = list(attendre_couleurs)

        # Phase de déplacement
        tracé.déplacer(paires)

        # Phase finale
        tracé.aspirer(joueurs)
        fatigués = tracé.fatiguer()
        for joueur in joueurs:
            joueur.client.afficher_fatigue(tracé, fatigués)

        # Détection de la fin de partie
        fin_de_partie = (max(tracé.positions.values()) >= tracé.arrivée)

    # Fin de la partie
    for joueur in joueurs:
        joueur.client.afficher(tracé)
        joueur.client.ordre(tracé.ordre())


def client_console(adresse, port):
    client = ClientConsole(adresse, port)
    client.jouer()


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)
    if len(sys.argv) == 2 or (len(sys.argv) > 2 and sys.argv[1] == '-c'):
        if len(sys.argv) == 3:
            client_console(socket.gethostname(), int(sys.argv[2]))
        elif len(sys.argv) == 4:
            client_console(sys.argv[2], int(sys.argv[3]))
        else:
            client_console(socket.gethostname(), int(sys.argv[1]))

    else:
        nb_humains = 1
        if len(sys.argv) > 2 and sys.argv[1] == '-h':
            nb_humains = min(4, max(1, int(sys.argv[2])))
        principal(nb_humains)
