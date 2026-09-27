import express from "express";
import path from "node:path";
import fs from "node:fs";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const app = express();
app.use(express.json({ limit: "2mb" }));
app.use(express.static(path.join(__dirname, "public")));

const JARVIS_CORE = fs.readFileSync(
  path.join(__dirname, "jarvis_core.md"),
  "utf8"
);

const MCP_READ_TOOLS = [
  "wordpress_health",
  "wordpress_current_user",
  "wordpress_get_page",
  "diagnose",
  "diagnose_symptom",
  "repair_urgency",
  "avtohirurg_protocol",
  "diagnostic_12_points",
  "client_conclusion",
  "checklist"
];

function buildMcpToolConfig() {
  const serverUrl = (process.env.AVTOHIRURG_MCP_URL || "").trim();
  if (!serverUrl) return [];

  const tool = {
    type: "mcp",
    server_label: "avtohirurg",
    server_url: serverUrl,
    allowed_tools: MCP_READ_TOOLS,
    require_approval: "never"
  };

  const token = (process.env.AVTOHIRURG_MCP_TOKEN || "").trim();
  if (token) {
    tool.headers = { Authorization: `Bearer ${token}` };
  }

  return [tool];
}

app.get("/health", (_req, res) =>
  res.json({
    ok: true,
    service: "avtohirurg-jarvis-voice",
    core_loaded: true,
    mcp_configured: Boolean((process.env.AVTOHIRURG_MCP_URL || "").trim()),
    mcp_read_tools: MCP_READ_TOOLS
  })
);

app.post("/api/session", async (req, res) => {
  const apiKey = process.env.OPENAI_API_KEY;
  if (!apiKey) return res.status(503).json({ error: "OPENAI_API_KEY is not configured" });

  const sdp = req.body?.sdp;
  if (typeof sdp !== "string" || !sdp.trim()) {
    return res.status(400).json({ error: "SDP offer is required" });
  }

  try {
    const response = await fetch("https://api.openai.com/v1/live/sessions", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${apiKey}`,
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        session: {
          model: "gpt-live-1",
          instructions:
            JARVIS_CORE +
            "\n\nДополнительные правила голосового runtime: если действие меняет сайт, данные или настройки, сначала запроси подтверждение владельца. MCP подключается отдельным безопасным каналом после установления Live-сессии; не раскрывай секреты клиенту."
        },
        transport: { type: "webrtc", sdp }
      })
    });

    const data = await response.json();
    if (!response.ok) {
      console.error("OpenAI Live error:", data);
      return res.status(response.status).json(data);
    }
    res.status(201).json(data);
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: "Failed to create Live session" });
  }
});

const port = Number(process.env.PORT || 3000);
app.listen(port, "0.0.0.0", () =>
  console.log("Jarvis voice listening on " + port)
);
// Railway redeploy trigger: MCP Live session compatibility fix is on main.
