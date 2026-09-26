import express from "express";
import OpenAI from "openai";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const app = express();
app.use(express.json({limit:"2mb"}));
app.use(express.static(path.join(__dirname,"public")));

const client = new OpenAI({ apiKey: process.env.OPENAI_API_KEY });

app.get("/health", (_req,res) => res.json({ok:true,service:"avtohirurg-jarvis-voice"}));

app.post("/api/session", async (req,res) => {
  if (!process.env.OPENAI_API_KEY) {
    return res.status(503).json({error:"OPENAI_API_KEY is not configured"});
  }
  if (typeof req.body?.sdp !== "string" || !req.body.sdp.trim()) {
    return res.status(400).json({error:"SDP offer is required"});
  }
  try {
    const live = await client.live.create({
      session: {
        model: "gpt-live-1",
        instructions:
          "Ты Автохирург-Jarvis — голосовой AI-помощник бизнеса Автохирург. " +
          "Говори по-русски, кратко и уверенно. Не выдумывай факты. " +
          "Для диагностических и рабочих задач опирайся на проверенные данные. " +
          "Если действие меняет сайт, данные или настройки, сначала запроси подтверждение владельца."
      },
      transport: { type: "webrtc", sdp: req.body.sdp }
    });
    res.json({session:live.session,transport:live.transport});
  } catch (err) {
    console.error(err);
    res.status(500).json({error:"Failed to create Live session"});
  }
});

const port = Number(process.env.PORT || 3000);
app.listen(port, "0.0.0.0", () => console.log("Jarvis voice listening on "+port));
