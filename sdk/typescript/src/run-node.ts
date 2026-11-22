// Lance votre bot depuis un terminal, sans navigateur (Node.js >= 22.18) :
//   node src/run-node.ts --token VOTRE_TOKEN --level 1
//   node src/run-node.ts --token VOTRE_TOKEN --mode campaign --url ws://192.168.1.10:8000

import { parseArgs } from "node:util";

import { decide } from "./bot.ts";
import { play } from "./client.ts";

const { values } = parseArgs({
  options: {
    token: { type: "string" },
    url: { type: "string", default: "ws://localhost:8000" },
    mode: { type: "string", default: "practice" },
    level: { type: "string", default: "1" },
    seed: { type: "string" },
  },
});

if (!values.token) {
  console.error("Usage : node src/run-node.ts --token VOTRE_TOKEN [--level 1] [--mode campaign]");
  process.exit(1);
}

try {
  await play(decide, {
    token: values.token,
    url: values.url,
    mode: values.mode === "campaign" ? "campaign" : "practice",
    level: Number(values.level),
    seed: values.seed !== undefined ? Number(values.seed) : undefined,
  });
} catch (error) {
  console.error((error as Error).message);
  process.exit(1);
}
