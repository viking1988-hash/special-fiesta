import express from "express";
import path from "node:path";
import fs from "node:fs";
import crypto from "node:crypto";
import { fileURLToPath } from "node:url";
import WebSocket from "ws";

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

const TOOL_SCHEMAS = {
  wordpress_health: {
    description: "Проверяет доступность WordPress REST API без изменения сайта.",
    parameters: { type: "object", properties: {}, additionalProperties: false }
  },
  wordpress_current_user: {
    description: "Проверяет авторизацию WordPress Application Password без изменения сайта.",
    parameters: { type: "object", properties: {}, additionalProperties: false }
  },
  wordpress_get_page: {
    description: "Читает страницу WordPress по ID без изменения сайта.",
    parameters: {
      type: "object",
      properties: { page_id: { type: "integer", description: "ID страницы WordPress" } },
      required: ["page_id"],
      additionalProperties: false
    }
  },
  diagnose: {
    description: "Возвращает методологический материал Автохирурга для указанной услуги и аудитории.",
    parameters: {
      type: "object",
      properties: {
        service: { type: "string" },
        audience: { type: "string" }
      },
      required: ["service", "audience"],
      additionalProperties: false
    }
  },
  diagnose_symptom: {
    description: "Выполняет предварительный анализ автомобильного симптома по правилам Автохирурга. Это не окончательный диагноз.",
    parameters: {
      type: "object",
      properties: {
        symptom: { type: "string" },
        car: { type: "string" }
      },
      required: ["symptom"],
      additionalProperties: false
    }
  },
  repair_urgency: {
    description: "Оценивает срочность проверки по жалобе и автомобилю. Это предварительная оценка, а не диагноз.",
    parameters: {
      type: "object",
      properties: {
        symptom: { type: "string" },
        car: { type: "string" }
      },
      required: ["symptom"],
      additionalProperties: false
    }
  },
  avtohirurg_protocol: {
    description: "Формирует единый протокол проверки: факты, гипотезы, проверки, доказательства и решение.",
    parameters: {
      type: "object",
      properties: {
        symptom: { type: "string" },
        car: { type: "string" },
        diagnostic_results: { type: "string" }
      },
      required: ["symptom"],
      additionalProperties: false
    }
  },
  diagnostic_12_points: {
    description: "Запускает 12-пунктный диагностический протокол Автохирурга.",
    parameters: {
      type: "object",
      properties: {
        symptom: { type: "string" },
        car: { type: "string" }
      },
      required: ["symptom"],
      additionalProperties: false
    }
  },
  client_conclusion: {
    description: "Формирует клиентское заключение только из переданных подтверждённых данных и доказательств.",
    parameters: {
      type: "object",
      properties: {
        car: { type: "string" },
        symptom: { type: "string" },
        confirmed_faults: { type: "string" },
        evidence: { type: "string" },
        recommended_repairs: { type: "string" },
        can_postpone: { type: "string" }
      },
      required: ["car", "symptom"],
      additionalProperties: false
    }
  },
  checklist: {
    description: "Возвращает 12-пунктный чек-лист Автохирурга.",
    parameters: { type: "object", properties: {}, additionalProperties: false }
  }
};

function buildDelegatedTools() {
  return MCP_READ_TOOLS.map((name) => ({
    type: "function",
    name,
    description: TOOL_SCHEMAS[name].description,
    parameters: TOOL_SCHEMAS[name].parameters
  }));
}

function env(name) {
  return (process.env[name] || "").trim();
}

function safeJson(value) {
  try {
    return JSON.stringify(value);
  } catch {
    return JSON.stringify({ error: "Unable to serialize tool result" });
  }
}

function parseMaybeJson(text) {
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

class AvtohirurgMcpClient {
  constructor() {
    this.url = env("AVTOHIRURG_MCP_URL");
    this.token = env("AVTOHIRURG_MCP_TOKEN");
    this.sessionId = "";
    this.requestId = 0;
    this.initPromise = null;
  }

  get configured() {
    return Boolean(this.url && this.token);
  }

  async request(method, params = {}, { initialize = false } = {}) {
    if (!this.configured) {
      throw new Error("Avtohirurg MCP is not configured on the server");
    }

    const headers = {
      Authorization: `Bearer ${this.token}`,
      "Content-Type": "application/json",
      Accept: "application/json, text/event-stream"
    };

    if (this.sessionId && !initialize) {
      headers["Mcp-Session-Id"] = this.sessionId;
    }

    const body = {
      jsonrpc: "2.0",
      id: ++this.requestId,
      method,
      params
    };

    const response = await fetch(this.url, {
      method: "POST",
      headers,
      body: JSON.stringify(body)
    });

    const responseText = await response.text();
    if (!response.ok) {
      throw new Error(`MCP HTTP ${response.status}: ${responseText.slice(0, 1200)}`);
    }

    const sessionId = response.headers.get("mcp-session-id");
    if (sessionId) this.sessionId = sessionId;

    if (!responseText.trim()) return {};
    if (responseText.trim().startsWith("data:")) {
      const dataLines = responseText
        .split(/\r?\n/)
        .filter((line) => line.startsWith("data:"))
        .map((line) => line.slice(5).trim())
        .filter(Boolean);
      const last = dataLines[dataLines.length - 1];
      return last ? JSON.parse(last) : {};
    }

    return JSON.parse(responseText);
  }

  async initialize() {
    if (this.initPromise) return this.initPromise;
    this.initPromise = (async () => {
      await this.request(
        "initialize",
        {
          protocolVersion: "2025-06-18",
          capabilities: {},
          clientInfo: {
            name: "avtohirurg-jarvis",
            version: "1.0.0"
          }
        },
        { initialize: true }
      );

      await fetch(this.url, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${this.token}`,
          "Content-Type": "application/json",
          Accept: "application/json, text/event-stream",
          ...(this.sessionId ? { "Mcp-Session-Id": this.sessionId } : {})
        },
        body: JSON.stringify({
          jsonrpc: "2.0",
          method: "notifications/initialized",
          params: {}
        })
      });
    })().catch((error) => {
      this.initPromise = null;
      throw error;
    });
    return this.initPromise;
  }

  async call(name, args) {
    if (!MCP_READ_TOOLS.includes(name)) {
      throw new Error(`Tool is not allowed: ${name}`);
    }
    await this.initialize();
    const result = await this.request("tools/call", {
      name,
      arguments: args || {}
    });
    if (result.error) {
      throw new Error(result.error.message || `MCP tool error: ${safeJson(result.error)}`);
    }
    return result.result ?? result;
  }
}

const mcpClient = new AvtohirurgMcpClient();
const liveSessions = new Map();

function closeSideband(sessionId) {
  const entry = liveSessions.get(sessionId);
  if (!entry) return;
  try { entry.ws.close(); } catch {}
  liveSessions.delete(sessionId);
}

async function executeTool(name, args) {
  console.log(`[JARVIS_TOOL] ${name}`);
  const result = await mcpClient.call(name, args);
  return typeof result === "string" ? result : safeJson(result);
}

function sendSideband(ws, payload) {
  if (ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify(payload));
  }
}

function attachSideband(sessionId, apiKey) {
  if (!sessionId || !apiKey) return Promise.resolve(false);
  if (liveSessions.has(sessionId)) return Promise.resolve(true);

  return new Promise((resolve) => {
    const url = `wss://api.openai.com/v1/live/sessions/${encodeURIComponent(sessionId)}/attach`;
    const ws = new WebSocket(url, {
      headers: {
        Authorization: `Bearer ${apiKey}`
      }
    });

    const timeout = setTimeout(() => {
      console.error("[JARVIS_SIDEBAND] attach timeout");
      try { ws.close(); } catch {}
      resolve(false);
    }, 10000);

    ws.on("open", () => {
      clearTimeout(timeout);
      liveSessions.set(sessionId, { ws });
      console.log(`[JARVIS_SIDEBAND] attached ${sessionId}`);
      resolve(true);
    });

    ws.on("message", async (raw) => {
      let envelope;
      try {
        envelope = JSON.parse(raw.toString());
      } catch {
        return;
      }

      const event = envelope?.type === "response.event" ? envelope.event : envelope;
      if (!event) return;

      if (event.type === "response.output_item.done" && event.item?.type === "function_call") {
        const callId = event.item.call_id;
        const name = event.item.name;
        let args = {};
        try {
          args = event.item.arguments ? JSON.parse(event.item.arguments) : {};
        } catch (error) {
          const output = safeJson({ ok: false, error: `Invalid tool arguments: ${error.message}` });
          sendSideband(ws, {
            type: "response.item.create",
            item: { type: "function_call_output", call_id: callId, output }
          });
          sendSideband(ws, { type: "response.create" });
          return;
        }

        try {
          const output = await executeTool(name, args);
          sendSideband(ws, {
            type: "response.item.create",
            item: {
              type: "function_call_output",
              call_id: callId,
              output
            }
          });
        } catch (error) {
          console.error("[JARVIS_TOOL_ERROR]", name, error.message);
          sendSideband(ws, {
            type: "response.item.create",
            item: {
              type: "function_call_output",
              call_id: callId,
              output: safeJson({ ok: false, error: error.message })
            }
          });
        }

        sendSideband(ws, { type: "response.create" });
      }
    });

    ws.on("error", (error) => {
      clearTimeout(timeout);
      console.error("[JARVIS_SIDEBAND] error", error.message);
      if (!liveSessions.has(sessionId)) resolve(false);
    });

    ws.on("close", () => {
      clearTimeout(timeout);
      liveSessions.delete(sessionId);
      console.log(`[JARVIS_SIDEBAND] closed ${sessionId}`);
    });
  });
}

app.get("/health", (_req, res) =>
  res.json({
    ok: true,
    service: "avtohirurg-jarvis-voice",
    core_loaded: true,
    mcp_configured: mcpClient.configured,
    mcp_read_tools: MCP_READ_TOOLS,
    delegated_tools: buildDelegatedTools().map((tool) => tool.name),
    sideband: true
  })
);

app.post("/api/session", async (req, res) => {
  const apiKey = env("OPENAI_API_KEY");
  if (!apiKey) {
    return res.status(503).json({ error: "OPENAI_API_KEY is not configured" });
  }

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
            "\n\nГолосовой runtime: говори кратко и естественно. Для диагностики сначала используй диагностические инструменты. Для чтения WordPress используй read-only инструменты. Любое изменение сайта, данных или настроек требует явного подтверждения владельца до выполнения.",
          delegation: {
            type: "responses",
            responses: {
              model: env("JARVIS_BACKEND_MODEL") || "gpt-6-luna",
              instructions:
                JARVIS_CORE +
                "\n\nBackend-инструкции: используй только доступные read-only инструменты Автохирурга. Не утверждай факт без проверки. Для WordPress сначала читай состояние. Никаких изменений сайта через эти инструменты. Возвращай краткий проверяемый результат. MCP-секрет никогда не передавай модели или клиенту.",
              tools: buildDelegatedTools(),
              tool_choice: "auto",
              parallel_tool_calls: false
            }
          }
        },
        transport: { type: "webrtc", sdp }
      })
    });

    const data = await response.json();
    if (!response.ok) {
      console.error("OpenAI Live error:", data);
      return res.status(response.status).json(data);
    }

    const sessionId = data?.session?.id || data?.id;
    if (sessionId) {
      attachSideband(sessionId, apiKey).catch((error) =>
        console.error("[JARVIS_SIDEBAND] attach failed", error.message)
      );
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
