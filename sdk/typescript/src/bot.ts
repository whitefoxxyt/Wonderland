// Votre bot. Seule la fonction decide() est à écrire.
// Elle reçoit l'observation du tick et doit renvoyer une action.

import type { Action, Observation } from "./types";

const MOVES: Action[] = ["MOVE_UP", "MOVE_DOWN", "MOVE_LEFT", "MOVE_RIGHT"];

export function decide(obs: Observation): Action {
  // Exemple naïf : marche au hasard. À vous de faire mieux !
  void obs;
  return MOVES[Math.floor(Math.random() * MOVES.length)];
}
