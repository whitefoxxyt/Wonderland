// Client Wonderland : connecte votre fonction decide() au serveur de jeu.
// Fonctionne dans le navigateur (Angular) et dans Node.js >= 22 (WebSocket natif).
// Vous n'avez rien à modifier ici : écrivez votre algorithme dans bot.ts.

import type { Decide, RunEnd, ServerMessage } from "./types";

export interface PlayOptions {
  token: string;
  url?: string; // "ws://localhost:8000" par défaut
  mode?: "practice" | "campaign";
  level?: number; // mode practice uniquement
  seed?: number; // practice : rejoue exactement la même partie
  log?: (text: string) => void; // console.log par défaut
  onMessage?: (message: ServerMessage) => void; // pour afficher la partie dans votre UI
}

/** Joue une partie complète ; la Promise se résout avec le message de fin (score, succès…). */
export function play(decide: Decide, options: PlayOptions): Promise<RunEnd> {
  const url = (options.url ?? "ws://localhost:8000").replace(/\/$/, "");
  const mode = options.mode ?? "practice";
  const log = options.log ?? ((text: string) => console.log(text));
  const params = new URLSearchParams({ token: options.token, mode });
  if (mode === "practice") params.set("level", String(options.level ?? 1));
  if (options.seed !== undefined) params.set("seed", String(options.seed));

  return new Promise<RunEnd>((resolve, reject) => {
    const ws = new WebSocket(`${url}/ws/bot?${params.toString()}`);
    let finished = false;
    const finish = (fn: () => void) => {
      if (finished) return;
      finished = true;
      fn();
      ws.close();
    };

    ws.onmessage = async (event: MessageEvent) => {
      const text = typeof event.data === "string" ? event.data : await (event.data as Blob).text();
      const message = JSON.parse(text) as ServerMessage;
      options.onMessage?.(message);

      switch (message.type) {
        case "observation": {
          let action;
          try {
            action = await decide(message.data);
          } catch (error) {
            console.error("Erreur dans decide() :", error); // la partie continue avec WAIT
            action = "WAIT";
          }
          ws.send(JSON.stringify({ type: "action", tick: message.tick, action }));
          break;
        }
        case "hello":
          log(`Partie ${message.run_id} (${message.mode}) niveaux ${message.levels.join(", ")}`);
          break;
        case "level_start":
          log(`→ Niveau ${message.level} : ${message.name}${message.seed !== null ? ` (seed ${message.seed})` : ""}`);
          break;
        case "level_end":
          log(`  ${message.status} en ${message.ticks} ticks, PV ${message.hp}`);
          break;
        case "run_end":
          log(`Fin de partie : ${message.status}, ${message.score} pts, succès : ${message.achievements.join(", ") || "aucun"}`);
          finish(() => resolve(message));
          break;
        case "error":
          finish(() => reject(new Error(message.message)));
          break;
      }
    };
    ws.onerror = () => finish(() => reject(new Error(`Impossible de joindre ${url}`)));
    ws.onclose = () => finish(() => reject(new Error("Connexion fermée par le serveur")));
  });
}
