// Types du protocole Wonderland (miroir de backend/wonderland/engine/observation.py
// et backend/wonderland/runs/protocol.py). Un test Python vérifie qu'ils restent synchronisés.

export type Action =
  | "MOVE_UP"
  | "MOVE_DOWN"
  | "MOVE_LEFT"
  | "MOVE_RIGHT"
  | "ATTACK"
  | "SHOOT"
  | "PARRY"
  | "WAIT";

export type Direction = "UP" | "DOWN" | "LEFT" | "RIGHT";
export type MobState = "IDLE" | "WINDUP" | "CHARGING" | "STUNNED";

export interface LevelInfo {
  id: number;
  name: string;
  max_ticks: number;
  ticks_left: number;
  vision_radius: number | null; // null = vision totale
  win_condition: "exit" | "boss";
}

export interface You {
  id: number;
  x: number;
  y: number;
  hp: number;
  max_hp: number;
  facing: Direction;
  weapon: "KNIFE" | "SUGAR_LAUNCHER";
  shoot_cooldown: number;
  hats: number;
}

export interface Mob {
  id: number;
  kind: string; // "dormouse" | "march_hare" | "card_guard" | "card_archer" | "queen"
  x: number;
  y: number;
  hp: number;
  max_hp: number;
  facing: Direction;
  state: MobState; // WINDUP = frappera au prochain tick
  state_ticks: number;
  boss: boolean;
}

export interface Item {
  id: number;
  kind: "HAT" | "POTION" | "LAUNCHER";
  x: number;
  y: number;
}

export interface Trap {
  x: number;
  y: number;
  active_this_turn: boolean; // blessera qui se tient dessus à la fin de ce tick
  next_active_in: number; // 0 = actif ce tick
  period: number;
  active_for: number;
  damage: number;
}

export interface Projectile {
  id: number;
  x: number;
  y: number;
  direction: Direction;
  speed: number; // cases par tick
  hostile: boolean;
  kind: string;
}

export interface GameEvent {
  type: string; // "PlayerMoved", "DamageDealt", "MobKilled"…
  [field: string]: unknown;
}

/**
 * Ce que voit votre bot à chaque tick.
 * grid[y][x] : '#' mur, '.' sol, '^' piège, '~' brume, 'E' sortie, '?' inconnu.
 */
export interface Observation {
  tick: number;
  status: string;
  level: LevelInfo;
  you: You;
  width: number;
  height: number;
  grid: string[];
  mobs: Mob[];
  items: Item[];
  traps: Trap[];
  projectiles: Projectile[];
  events: GameEvent[];
}

// ---------- messages du serveur ----------

export interface Hello {
  type: "hello";
  protocol_version: number;
  run_id: string;
  team: string;
  mode: "practice" | "campaign";
  levels: number[];
  tick_timeout: number;
}

export interface LevelStart {
  type: "level_start";
  level: number;
  name: string;
  seed: number | null;
}

export interface ObservationMessage {
  type: "observation";
  run_id: string;
  level: number;
  tick: number;
  data: Observation;
}

export interface LevelEnd {
  type: "level_end";
  level: number;
  status: "WON" | "DEAD" | "TIMEOUT";
  ticks: number;
  hp: number;
}

export interface RunEnd {
  type: "run_end";
  status: string;
  levels_completed: number[];
  total_ticks: number;
  score: number;
  achievements: string[];
  reason: string;
}

export interface ErrorMessage {
  type: "error";
  message: string;
}

export type ServerMessage =
  | Hello
  | LevelStart
  | ObservationMessage
  | LevelEnd
  | RunEnd
  | ErrorMessage;

/** Votre algorithme : reçoit l'observation, renvoie une action (éventuellement via une Promise). */
export type Decide = (obs: Observation) => Action | Promise<Action>;
