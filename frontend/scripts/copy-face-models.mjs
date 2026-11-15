// Copies the face-api.js model weights into public/models so they are served from your own domain (no third-party CDN).
import { cpSync, existsSync, mkdirSync, readdirSync } from "node:fs";
import { join } from "node:path";
const src = join("node_modules", "@vladmandic", "face-api", "model");
const dst = join("public", "models");
const need = ["tiny_face_detector_model", "face_landmark_68_tiny_model", "face_recognition_model"];
if (!existsSync(src)) { console.log("face-api models not found, skipping"); process.exit(0); }
mkdirSync(dst, { recursive: true });
for (const f of readdirSync(src)) if (need.some((n) => f.startsWith(n))) cpSync(join(src, f), join(dst, f));
console.log("face models copied:", readdirSync(dst).join(", "));
