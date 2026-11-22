// Service Angular : lance votre bot depuis l'application et expose l'état de la partie en signals.
// À copier dans src/app/ d'un projet Angular (17+), avec le dossier sdk/ (client.ts, types.ts, bot.ts).

import { Injectable, signal } from "@angular/core";

import { decide } from "../sdk/bot";
import { play, type PlayOptions } from "../sdk/client";
import type { Observation, RunEnd } from "../sdk/types";

@Injectable({ providedIn: "root" })
export class WonderlandBotService {
  readonly running = signal(false);
  readonly logs = signal<string[]>([]);
  readonly observation = signal<Observation | null>(null);
  readonly result = signal<RunEnd | null>(null);

  async start(options: Omit<PlayOptions, "log" | "onMessage">): Promise<void> {
    if (this.running()) return;
    this.running.set(true);
    this.logs.set([]);
    this.result.set(null);
    try {
      const end = await play(decide, {
        ...options,
        log: (text) => this.logs.update((lines) => [...lines, text]),
        onMessage: (message) => {
          if (message.type === "observation") this.observation.set(message.data);
        },
      });
      this.result.set(end);
    } catch (error) {
      this.logs.update((lines) => [...lines, `Erreur : ${(error as Error).message}`]);
    } finally {
      this.running.set(false);
    }
  }
}
