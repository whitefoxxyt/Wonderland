// Composant Angular minimal : formulaire de lancement + vue ASCII de ce que voit le bot + journal.

import { Component, computed, inject, signal } from "@angular/core";
import { FormsModule } from "@angular/forms";

import { WonderlandBotService } from "./wonderland-bot.service";

@Component({
  selector: "app-bot-runner",
  standalone: true,
  imports: [FormsModule],
  template: `
    <form (ngSubmit)="start()">
      <input name="url" [(ngModel)]="url" placeholder="ws://serveur:8000" />
      <input name="token" [(ngModel)]="token" placeholder="token de l'équipe" />
      <select name="mode" [(ngModel)]="mode">
        <option value="practice">Entraînement</option>
        <option value="campaign">Campagne</option>
      </select>
      @if (mode === "practice") {
        <input name="level" type="number" min="1" max="5" [(ngModel)]="level" />
      }
      <button type="submit" [disabled]="bot.running()">Lancer</button>
    </form>

    @if (bot.observation(); as obs) {
      <p>Niveau {{ obs.level.id }} — tick {{ obs.tick }} — PV {{ obs.you.hp }}/{{ obs.you.max_hp }}</p>
      <pre class="grid">{{ view() }}</pre>
    }
    @if (bot.result(); as end) {
      <p><strong>{{ end.status }}</strong> — {{ end.score }} pts — {{ end.achievements.join(", ") }}</p>
    }
    <pre class="logs">{{ bot.logs().join("\\n") }}</pre>
  `,
  styles: [".grid { font-family: monospace; line-height: 1; } .logs { max-height: 200px; overflow: auto; }"],
})
export class BotRunnerComponent {
  readonly bot = inject(WonderlandBotService);
  url = "ws://localhost:8000";
  token = "";
  mode: "practice" | "campaign" = "practice";
  level = 1;

  /** Grille ASCII avec le joueur (@) et les mobs (m) superposés. */
  readonly view = computed(() => {
    const obs = this.bot.observation();
    if (!obs) return "";
    const rows = obs.grid.map((row) => row.split(""));
    for (const mob of obs.mobs) rows[mob.y][mob.x] = mob.boss ? "Q" : "m";
    rows[obs.you.y][obs.you.x] = "@";
    return rows.map((row) => row.join("")).join("\n");
  });

  start(): void {
    void this.bot.start({ url: this.url, token: this.token, mode: this.mode, level: this.level });
  }
}
