#!/usr/bin/env python3

# Simple test script for the new display functionality
import sys
import os.path
sys.path.insert(0, os.path.dirname(__file__))

from flamme_rouge import *

def test_display_modes():
    """Test the new display modes with a simple track"""
    print("=== Testing New Display Modes ===\n")
    
    # Create a test track
    cases = []
    for i in range(30):
        if i < 8:
            cases.append(Case(Pente.plat))
        elif i < 16:
            cases.append(Case(Pente.col))
        elif i < 24:
            cases.append(Case(Pente.descente))
        else:
            cases.append(Case(Pente.plat))

    tracé = Tracé(cases, 2, 28, 30)
    
    # Add some test riders
    try:
        import yaml
        joueur_test = Robot('blue', 'teams/team1.yaml', 1)
        pion1 = Pion(Profil.sprinteur, joueur_test)  
        pion2 = Pion(Profil.rouleur, joueur_test)
        
        tracé.poser(pion1, 10)
        tracé.poser(pion2, 8)
        
        print("1. Window mode (original behavior):")
        tracé.afficher(mode='window')
        
        print("\n2. Full track mode:")
        tracé.afficher(mode='full', max_width=160)
        
        print("\n3. Wrapped display mode:")
        tracé.afficher(mode='wrapped', max_width=80)
        
        print("\n4. Overview mode:")
        tracé.afficher(mode='overview')
        
        print("\nTest completed successfully!")
        
    except Exception as e:
        print(f"Test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_display_modes()
