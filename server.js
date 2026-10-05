import express from "express";
import path from "node:path";
import fs from "node:fs";
import crypto from "node:crypto";
import { fileURLToPath } from "node:url";
import WebSocket from "ws";
import pg from "pg";
const { Pool } = pg;

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const app = express();
const db = process.env.DATABASE_URL ? new Pool({ connectionString: process.env.DATABASE_URL, ssl: false, max: 5 }) : null;
async function initOpsDb() {
  if (!db) return;
  await db.query(`CREATE TABLE IF NOT EXISTS jarvis_cases (
    id text PRIMARY KEY, vin text, plate text, car text, mileage text, status text NOT NULL,
    complaint text, finding text, evidence text, recommendation text, approved_amount text,
    approval_ref text, repair_result text, control_check text, media_url text, next_service text,
    warranty text, client_handover text, payload jsonb NOT NULL, created_at timestamptz DEFAULT now(),
    updated_at timestamptz DEFAULT now()
  )`);
  await db.query(`CREATE INDEX IF NOT EXISTS jarvis_cases_vehicle_idx ON jarvis_cases(vin, plate)`);
  await db.query(`CREATE TABLE IF NOT EXISTS jarvis_parts (
    id bigserial PRIMARY KEY, case_id text REFERENCES jarvis_cases(id) ON DELETE CASCADE,
    part_name text NOT NULL, availability text DEFAULT 'unknown', supplier text, price numeric DEFAULT 0,
    eta text, created_at timestamptz DEFAULT now()
  )`);
  await db.query(`CREATE TABLE IF NOT EXISTS jarvis_followups (
    id bigserial PRIMARY KEY, case_id text REFERENCES jarvis_cases(id) ON DELETE CASCADE,
    due_at timestamptz, reason text NOT NULL, status text DEFAULT 'planned', created_at timestamptz DEFAULT now()
  )`);
}
initOpsDb().catch(e => console.error("[OPS_DB_INIT]", e.message));
app.use(express.json({ limit: "2mb" }));
app.use((req,res,next)=>{if(req.path==="/"||req.path==="/owner.html"){res.set("Cache-Control","no-store, no-cache, must-revalidate, proxy-revalidate");res.set("Pragma","no-cache");res.set("Expires","0");}next();});
app.use(express.static(path.join(__dirname, "public"),{etag:false,maxAge:0}));

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
  "checklist",
  "generate_client_diagnostic_pdf"
];

const MCP_APPROVAL_TOOLS = ["wordpress_update_page"];

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
  },
  generate_client_diagnostic_pdf: {
    description: "Формирует клиентский PDF по боевому шаблону Carbone V2 из структурированного JSON диагностики Автохирурга.",
    parameters: {
      type: "object",
      properties: {
        data_json: { type: "string", description: "JSON-строка с complaint, report, vehicle, diagnostic p1-p12, conclusion, media и specialist." },
        report_name: { type: "string", description: "Имя PDF-файла, например AH-2026-0001.pdf." }
      },
      required: ["data_json"],
      additionalProperties: false
    }
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
        .split(new RegExp("\\r?\\n"))
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

  async call(name, args, { approved = false } = {}) {
    const readAllowed = MCP_READ_TOOLS.includes(name);
    const approvalAllowed = approved && MCP_APPROVAL_TOOLS.includes(name);
    if (!readAllowed && !approvalAllowed) {
      throw new Error(`Tool is not allowed without approval: ${name}`);
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

const pendingApprovals = new Map();
const APPROVAL_TTL_MS = 5 * 60 * 1000;

function purgeExpiredApprovals() {
  const now = Date.now();
  for (const [id, proposal] of pendingApprovals) {
    if (now - proposal.createdAt > APPROVAL_TTL_MS) pendingApprovals.delete(id);
  }
}

function createApprovalProposal(action, args = {}) {
  purgeExpiredApprovals();
  const id = crypto.randomBytes(3).toString("hex").toUpperCase();
  pendingApprovals.set(id, { action, args, createdAt: Date.now() });
  console.log("[JARVIS_APPROVAL_CREATED]", id, action, args?.page_id || "");
  return id;
}

function consumeApprovalProposal(id) {
  const key = String(id || "").toUpperCase();
  const proposal = pendingApprovals.get(key);
  if (!proposal) return null;
  pendingApprovals.delete(key);
  if (Date.now() - proposal.createdAt > APPROVAL_TTL_MS) {
    console.log("[JARVIS_APPROVAL_EXPIRED]", key, proposal.action);
    return null;
  }
  console.log("[JARVIS_APPROVAL_CONSUMED]", key, proposal.action, proposal.args?.page_id || "");
  return proposal;
}

function cancelApprovalProposal(id) {
  const key = String(id || "").toUpperCase();
  const removed = pendingApprovals.delete(key);
  if (removed) console.log("[JARVIS_APPROVAL_CANCELLED]", key);
  return removed;
}

function normalizeTranscript(text) {
  return String(text || "")
    .toLowerCase()
    .replace(/[«»"']/g, "")
    .replace(/\s+/g, " ")
    .trim();
}

function fieldCase(caseData, key, fallback = "") {
  if (!caseData || typeof caseData !== "object" || Array.isArray(caseData)) return String(fallback || "").trim().slice(0, 4000);
  return String(caseData[key] ?? fallback ?? "").trim().slice(0, 4000);
}

function routeTranscriptTask(text, caseData = null) {
  const t = normalizeTranscript(text);
  if (!t) return null;

  // Connectivity check is handled directly by the MCP client. This avoids
  // sending a large delegated Responses request just to verify the backend.
  if (
    /(проверь|проверить|проверьте).*(подключени|связь|соединени).*(mcp|мсп|эмси)/i.test(t) ||
    /(mcp|мсп|эмси).*(подключен|доступен|работает|связь)/i.test(t)
  ) {
    return { name: "checklist", args: {} };
  }

  if (
    /(проверь|проверить|проверьте).*(состояние )?(wordpress|вордпресс|сайт)/i.test(t) ||
    /(состояние|доступность).*(wordpress|вордпресс)/i.test(t)
  ) {
    return { name: "wordpress_health", args: {} };
  }

  if (
    /(проверь|проверить|проверьте).*(авторизац|пользовател).*(wordpress|вордпресс)/i.test(t)
  ) {
    return { name: "wordpress_current_user", args: {} };
  }

  const pageMatch = t.match(/(?:страниц|page)\D{0,20}(\d{1,8})/i);
  if (
    /(проверь|проверить|проверьте|прочитай|прочитать).*(страниц|page).*(wordpress|вордпресс)?/i.test(t) &&
    pageMatch
  ) {
    return { name: "wordpress_get_page", args: { page_id: Number(pageMatch[1]) } };
  }

  if (/(12[- ]?пункт|двенадцат).*(диагност|протокол)/i.test(t)) {
    return { name: "diagnostic_12_points", args: { symptom: text } };
  }

  if (/(срочност|насколько срочно|можно ли ездить)/i.test(t)) {
    return { name: "repair_urgency", args: { symptom: text } };
  }

  if (/(разбери симптом|разобрать симптом|проведи диагностику|диагностируй)/i.test(t)) {
    return { name: "diagnose_symptom", args: { symptom: text } };
  }

  if (/(протокол автохирург|протокол проверки|сформируй протокол|составь протокол)/i.test(t)) {
    return { name: "avtohirurg_protocol", args: { symptom: text } };
  }

  if (/(тестов.*(?:диагностическ.*заключени|pdf)|(?:диагностическ.*заключени|pdf).*тестов)/i.test(t)) {
    const data = {
      complaint: "Стук в передней подвеске на неровностях, сильнее на малой скорости.",
      report: { number: "TEST-TIGUAN-001", date: "30.09.2026", datetime: "30.09.2026 17:00" },
      vehicle: { make_model: "Volkswagen Tiguan", plate: "ТЕСТ", vin: "TEST-VIN", mileage: "128 450 км" },
      diagnostic: Object.fromEntries(Array.from({ length: 12 }, (_, i) => ["p" + (i + 1), { result: i === 6 ? "Выявлен люфт правой передней стойки стабилизатора" : "Проверено", evidence: i === 10 ? "Механическая нагрузка воспроизвела характерный стук" : "Тестовый протокол Автохирурга" }])),
      conclusion: { confirmed_fault: "Люфт правой передней стойки стабилизатора", evidence: "Механическая нагрузка воспроизвела характерный стук", repair_now: "Заменить правую переднюю стойку стабилизатора", can_wait: "Остальные элементы передней подвески по текущей проверке замены не требуют", urgency: "Плановый ремонт", recommendation: "Заменить подтверждённо неисправную деталь и выполнить контрольную проверку", summary: "Неисправность подтверждена тестом. Замена остальных деталей без доказательства не требуется." },
      media: { url: "", note: "Тестовый документ — не является заключением по реальному автомобилю" },
      specialist: { name: "Автохирург — тест" }
    };
    return { name: "generate_client_diagnostic_pdf", args: { data_json: JSON.stringify(data), report_name: "Avtohirurg_Tiguan_TEST.pdf" } };
  }

  if (/(диагностическ.*pdf|pdf.*диагностическ)/i.test(t) && (/данные:/i.test(t) || (caseData && typeof caseData === "object" && !Array.isArray(caseData)))) {
    const safeCase = caseData && typeof caseData === "object" ? caseData : {};
    const field = (key, fallback = "") => String(safeCase[key] ?? fallback).trim().slice(0, 4000);
    const get = (label, next) => {
      const re = new RegExp(label + "\\s*([^,]+?)" + (next ? "(?=,\\s*(?:" + next + ")\\b|$)" : "(?=,|$)"), "i");
      return (text.match(re)?.[1] || "").trim();
    };
    const vehicle = field("car", get("автомобиль", "госномер|пробег|vin|жалоба"));
    const plate = field("plate", get("госномер", "пробег|vin|жалоба")).slice(0, 20);
    const mileage = field("mileage", get("пробег", "vin|жалоба")).slice(0, 20);
    const vin = field("vin", get("vin", "жалоба")).toUpperCase().slice(0, 17);
    const complaint = field("complaint", get("жалоба клиента", "доказательство|неисправность|срочность|рекомендация"));
    const evidence = field("evidence", get("доказательство", "неисправность|вывод|срочность|рекомендация"));
    const finding = field("finding", get("неисправность", "срочность|рекомендация"));
    const repairApproved = safeCase.repairApproved === true || String(safeCase.repairApproved || "").toLowerCase() === "true";
    const repairResult = field("repairResult", get("выполненный ремонт", "контрольная проверка|фото|видео"));
    const controlCheck = field("controlCheck", get("контрольная проверка", "фото|видео|финальная проверка"));
    if ((repairResult || controlCheck) && !repairApproved) return { error: "Нельзя фиксировать выполненный ремонт или контрольную проверку до согласования ремонта с клиентом." };
    const mediaUrl = field("mediaUrl", get("фото(?:/видео)?", "финальная проверка|следующий контроль"));
    const finalCheck = safeCase.finalCheck === true || String(safeCase.finalCheck || "").toLowerCase() === "true";
    const urgency = field("urgency", get("срочность", "рекомендация|ремонт согласован"));
    const recommendation = field("recommendation", get("рекомендация", "ремонт согласован|выполненный ремонт"));
    const nextService = field("nextService", get("следующий контроль", "гарантия|выдача клиенту"));
    const warranty = field("warranty", get("гарантия", "выдача клиенту"));
    const clientHandover = field("clientHandover", get("выдача клиенту", "дата завершения"));
    const clientName = field("clientName").slice(0, 120);
    const phone = field("phone").slice(0, 40);
    const orderNumber = field("orderNumber").slice(0, 80);
    const masterName = field("masterName").slice(0, 120);
    const arrivalDate = field("arrivalDate").slice(0, 40);
    const completionDate = field("completionDate").slice(0, 40);
    const laborHours = field("laborHours").slice(0, 40);
    const partsUsed = field("partsUsed");
    const approvedAmount = field("approvedAmount").slice(0, 40);
    const laborAmount = field("laborAmount").slice(0, 40);
    const partsAmount = field("partsAmount").slice(0, 40);
    const approvalRef = field("approvalRef").slice(0, 300);
    if (!vehicle || !complaint) return { error: "Для диагностического документа заполните автомобиль и жалобу клиента." };
    if (!evidence || !finding) return { error: "Сначала зафиксируйте доказательство и подтверждённую неисправность." };
    if (vin && !/^[A-HJ-NPR-Z0-9]{17}$/.test(vin)) return { error: "VIN должен содержать 17 допустимых символов без I, O и Q." };
    const mileageNumber = Number(String(mileage || "").replace(/[^0-9]/g, ""));
    if (mileage && (!Number.isFinite(mileageNumber) || mileageNumber < 1 || mileageNumber >= 3000000)) return { error: "Проверьте пробег автомобиля." };
    const closeReady = repairApproved && Boolean(repairResult) && Boolean(controlCheck);
    if (finalCheck && !closeReady) return { error: "Финальная проверка доступна только после согласования ремонта, выполненных работ и контрольной проверки." };
    const money = (value) => {
      const normalized = String(value || "").replace(/[^0-9.,-]/g, "").replace(",", ".");
      const parsed = Number.parseFloat(normalized);
      return Number.isFinite(parsed) && parsed >= 0 ? parsed : 0;
    };
    const approvedRub = money(approvedAmount);
    const laborRub = money(laborAmount);
    const partsRub = money(partsAmount);
    const actualRub = laborRub + partsRub;
    if (repairApproved && approvedRub <= 0) return { error: "Перед отметкой «ремонт согласован» укажите согласованную с клиентом сумму." };
    if (repairApproved && !approvalRef) return { error: "Для согласованного ремонта укажите доказательство согласования: звонок, сообщение или номер документа." };
    if (approvedRub > 0 && !approvalRef) return { error: "Для согласованной суммы укажите доказательство согласования: звонок, сообщение или номер документа." };
    if (actualRub > 0 && approvedRub <= 0) return { error: "Перед фиксацией стоимости работ или запчастей укажите согласованную с клиентом сумму." };
    if (approvedRub > 0 && actualRub > approvedRub) return { error: "Фактическая сумма " + actualRub + " ₽ превышает согласованные " + approvedRub + " ₽. Требуется новое согласование клиента." };
    const now = new Date();
    const stamp = now.toISOString().slice(0,10).replaceAll("-","");
    const data = {
      complaint: complaint || "Жалоба не указана",
      report: { number: orderNumber || "JARVIS-" + stamp, date: now.toLocaleDateString("ru-RU"), datetime: now.toLocaleString("ru-RU") },
      vehicle: { make_model: vehicle || "Не указано", plate: plate || "", vin: vin || "", mileage: mileage || "" },
      diagnostic: Object.fromEntries(Array.from({ length: 12 }, (_, i) => {
        const key = "p" + (i + 1);
        const point = safeCase.diagnostic?.[key];
        const result = String(point?.result || field("diagnostic_" + key + "_result") || "").trim().slice(0, 4000);
        const pointEvidence = String(point?.evidence || field("diagnostic_" + key + "_evidence") || "").trim().slice(0, 4000);
        return [key, {
          result: result || "Не зафиксировано",
          evidence: pointEvidence || (i === 10 && evidence ? evidence : "Доказательство по пункту не приложено")
        }];
      })),
      conclusion: {
        confirmed_fault: finding || "Не заполнено — требуется результат диагностики",
        evidence: evidence || "Не заполнено — требуется доказательство",
        repair_now: repairResult || recommendation || "Ремонт не назначен без подтверждённой неисправности",
        can_wait: "",
        urgency: urgency || "Определяется после диагностики",
        recommendation: recommendation || "Провести проверку и зафиксировать доказательство до ремонта",
        summary: finalCheck ? "Диагностический цикл завершён: неисправность доказана, ремонт согласован и выполнен, финальная контрольная проверка пройдена." : finding && evidence ? (repairApproved ? (repairResult && controlCheck ? "Неисправность доказана, ремонт согласован и выполнен. Контрольная проверка после ремонта зафиксирована." : "Неисправность и доказательство зафиксированы. Согласование ремонта отмечено в диагностической карте.") : "Неисправность зафиксирована вместе с доказательством. Следующий шаг — согласование ремонта с клиентом.") : "Черновик диагностического заключения. Сначала доказательство — потом ремонт."
      },
      media: { url: mediaUrl || "", note: controlCheck ? "Контрольная проверка после ремонта: " + controlCheck : "Фото/видео-доказательство не приложено" },
      client: { name: clientName, phone },
      service: { master: masterName, intake_at: arrivalDate, completed_at: completionDate, labor_hours: laborHours, parts_used: partsUsed, approved_amount: approvedAmount, labor_amount: laborAmount, parts_amount: partsAmount, approval_reference: approvalRef, next_service: nextService, warranty, client_handover: clientHandover },
      specialist: { name: masterName || "Автохирург" }
    };
    const safeName=(vehicle || "vehicle").replace(/[^a-zA-Z0-9А-Яа-я_-]+/g,"_").slice(0,40);
    return { name: "generate_client_diagnostic_pdf", args: { data_json: JSON.stringify(data), report_name: "Avtohirurg_"+safeName+"_"+stamp+".pdf" } };
  }



  if (/(заключени.*клиент|клиентск.*заключени|сформируй заключени|составь заключени)/i.test(t)) {
    const car = fieldCase(caseData, "car");
    const symptom = fieldCase(caseData, "complaint", text);
    const confirmedFaults = fieldCase(caseData, "finding");
    const evidence = fieldCase(caseData, "evidence");
    if (!car || !symptom) return { error: "Для клиентского заключения заполните автомобиль и жалобу клиента." };
    if (!confirmedFaults || !evidence) return { error: "Клиентское заключение формируется только после фиксации доказательства и подтверждённой неисправности." };
    return { name: "client_conclusion", args: { car, symptom, confirmed_faults: confirmedFaults, evidence, recommended_repairs: fieldCase(caseData, "recommendation"), can_postpone: fieldCase(caseData, "urgency") } };
  }

  if (/(чек[- ]?лист автохирург|покажи чек[- ]?лист|запусти чек[- ]?лист)/i.test(t)) {
    return { name: "checklist", args: {} };
  }

  const updatePageMatch = t.match(/(?:страниц|page)\D{0,20}(\d{1,8})/i);
  if (/(измени|обнови).*(страниц|page)/i.test(t) && updatePageMatch) {
    const pageId = Number(updatePageMatch[1]);
    const titleMatch = text.match(/(?:заголовок|title).*?(?:на|=)\s*[«"']?(.+?)[»"']?\s*$/i);
    const statusMatch = text.match(/(?:статус|status).*?(?:на|=)\s*(draft|pending|private|publish|черновик|опубликован(?:о|ный)?|приватн(?:ый|о)|на рассмотрении)\s*$/i);
    const statusMap = {
      "черновик": "draft",
      "опубликовано": "publish",
      "опубликованный": "publish",
      "приватный": "private",
      "приватно": "private",
      "на рассмотрении": "pending"
    };
    let fields = null;
    if (titleMatch) fields = { title: titleMatch[1].trim() };
    if (statusMatch) {
      const rawStatus = statusMatch[1].toLowerCase();
      fields = { status: statusMap[rawStatus] || rawStatus };
    }
    if (!fields) {
      return { approval_required: true, action: "unsupported_write_request", args: { page_id: pageId, request: text } };
    }
    return {
      approval_required: true,
      action: "wordpress_update_page",
      args: { page_id: pageId, fields, request: text }
    };
  }

  if (/(проверь|проверить|тест).*(подтверждени|approval|аппрув).*(запис|измен|wordpress|вордпресс)/i.test(t)) {
    return {
      approval_required: true,
      action: "approval_gate_test",
      args: { request: text }
    };
  }

  if (/(измени|обнови|удали|опубликуй|создай|запиши).*(wordpress|вордпресс|сайт|страниц)/i.test(t)) {
    return { approval_required: true, action: "unsupported_write_request", args: { request: text } };
  }

  return null;
}

async function routeTranscriptTaskToMcp(sessionId, ws, text) {
  const task = routeTranscriptTask(text, caseData);
  if (!task) return false;

  const entry = liveSessions.get(sessionId);
  if (!entry || entry.lastRoutedText === text) return false;
  entry.lastRoutedText = text;

  console.log("[JARVIS_TRANSCRIPT_ROUTE]", task.name, text);

  try {
    const output = await executeTool(task.name, task.args);
    let compact;
    if (task.name === "checklist" && /(подключени|связь|соединени).*(mcp|мсп|эмси)/i.test(normalizeTranscript(text))) {
      compact = "MCP подключён и отвечает. Проверка backend Автохирурга прошла успешно.";
    } else {
      const parsed = parseMaybeJson(output);
      const candidate =
        parsed?.structuredContent?.result ||
        parsed?.content?.find?.((item) => item?.type === "text")?.text ||
        (typeof parsed === "string" ? parsed : output);
      compact = String(candidate).replaceAll(String.fromCharCode(10), " ").slice(0, 1200);
    }
    sendSideband(ws, {
      type: "session.commentary.append",
      event_id: "route_" + crypto.randomUUID(),
      delegation_id: null,
      content: compact
    });
    console.log("[JARVIS_TRANSCRIPT_RESULT]", task.name);
  } catch (error) {
    console.error("[JARVIS_TRANSCRIPT_ERROR]", task.name, error.message);
    sendSideband(ws, {
      type: "session.commentary.append",
      event_id: "route_error_" + crypto.randomUUID(),
      delegation_id: null,
      content: "Не удалось выполнить проверку через backend: " + error.message
    });
  }
  return true;
}

function scheduleTranscriptRoute(sessionId, ws) {
  const entry = liveSessions.get(sessionId);
  if (!entry) return;

  clearTimeout(entry.transcriptTimer);
  entry.transcriptTimer = setTimeout(() => {
    const current = liveSessions.get(sessionId);
    if (!current || !current.inputTranscript) return;
    routeTranscriptTaskToMcp(sessionId, ws, current.inputTranscript).catch((error) => {
      console.error("[JARVIS_TRANSCRIPT_ROUTE_ERROR]", error.message);
    });
  }, 1200);
}

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
      headers: { Authorization: `Bearer ${apiKey}` }
    });

    const timeout = setTimeout(() => {
      console.error("[JARVIS_SIDEBAND] attach timeout");
      try { ws.close(); } catch {}
      resolve(false);
    }, 10000);

    ws.on("open", () => {
      clearTimeout(timeout);
      liveSessions.set(sessionId, {
        ws,
        inputTranscript: "",
        transcriptTimer: null,
        lastRoutedText: ""
      });
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

      console.log("[JARVIS_SIDEBAND_EVENT]", event.type);

      if (event.type === "session.input_transcript.delta") {
        const entry = liveSessions.get(sessionId);
        if (entry) {
          entry.inputTranscript = (entry.inputTranscript || "") + (event.delta || "");
          console.log("[JARVIS_INPUT_TRANSCRIPT]", event.delta || "");
          // Browser /api/route-transcript is the single MCP executor.
          // Sideband only observes transcript and carries Live audio/events,
          // preventing one spoken command from calling the same MCP tool twice.
        }
        return;
      }

      if (event.type === "session.delegation.created") {
        console.log("[JARVIS_DELEGATION_CREATED]", safeJson(event.delegation || {}));
      }

      // GPT-Live/Responses can surface function calls either as a completed
      // output item or as the final function-call-arguments event.
      const item = event.item?.type === "function_call" ? event.item : null;
      const isFunctionCallItem = event.type === "response.output_item.done" && item;
      const isFunctionCallArgumentsDone =
        event.type === "response.function_call_arguments.done" &&
        event.call_id &&
        event.name;

      if (!isFunctionCallItem && !isFunctionCallArgumentsDone) return;

      const callId = item?.call_id || event.call_id;
      const name = item?.name || event.name;
      const rawArguments = item?.arguments ?? event.arguments ?? "{}";

      let args = {};
      try {
        args = typeof rawArguments === "string"
          ? JSON.parse(rawArguments || "{}")
          : (rawArguments || {});
      } catch (error) {
        const output = safeJson({
          ok: false,
          error: `Invalid tool arguments: ${error.message}`
        });
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
    });

    ws.on("error", (error) => {
      clearTimeout(timeout);
      console.error("[JARVIS_SIDEBAND] error", error.message);
      if (!liveSessions.has(sessionId)) resolve(false);
    });

    ws.on("close", () => {
      clearTimeout(timeout);
      const entry = liveSessions.get(sessionId);
      if (entry?.transcriptTimer) clearTimeout(entry.transcriptTimer);
      liveSessions.delete(sessionId);
      console.log(`[JARVIS_SIDEBAND] closed ${sessionId}`);
    });
  });
}

function extractPdfResource(output) {
  let parsed = parseMaybeJson(output);
  if (parsed?.result) parsed = parsed.result;
  const content = Array.isArray(parsed?.content) ? parsed.content : [];
  for (const item of content) {
    if (item?.type === "resource" && item?.resource?.blob) {
      return { content: [{ type: "resource", resource: {
        uri: item.resource.uri || "file:diagnostic.pdf",
        mimeType: item.resource.mimeType || "application/pdf",
        blob: item.resource.blob
      }}]};
    }
    if (item?.type === "text" && typeof item.text === "string") {
      const nested = parseMaybeJson(item.text);
      const nestedContent = Array.isArray(nested?.content) ? nested.content : [];
      const resource = nestedContent.find((x) => x?.type === "resource" && x?.resource?.blob);
      if (resource) return { content: [resource] };
    }
  }
  return null;
}

function formatBrowserToolResult(task, output, transcript) {
  if (task.name === "checklist" && /(подключени|связь|соединени).*(mcp|мсп|эмси)/i.test(normalizeTranscript(transcript))) {
    return "MCP подключён и отвечает. Backend Автохирурга работает.";
  }
  const parsed = parseMaybeJson(output);
  const candidate =
    parsed?.structuredContent?.result ||
    parsed?.content?.find?.((item) => item?.type === "text")?.text ||
    (typeof parsed === "string" ? parsed : output);
  return String(candidate).replaceAll(String.fromCharCode(10), " ").slice(0, 1200);
}

app.post("/api/approval/confirm", async (req, res) => {
  const proposal = consumeApprovalProposal(req.body?.approval_id);
  if (!proposal) return res.status(404).json({ ok: false, error: "approval_not_found_or_expired" });

  if (proposal.action === "approval_gate_test") {
    console.log("[JARVIS_APPROVAL_GATE_TEST]", "confirmed_without_mutation");
    return res.json({
      ok: true,
      approved: true,
      executed: false,
      mutation: false,
      action: proposal.action,
      result: "Контур подтверждения работает. Данные WordPress не изменялись."
    });
  }

  if (proposal.action !== "wordpress_update_page") {
    return res.status(409).json({ ok: false, error: "write_action_not_supported", action: proposal.action });
  }

  // Execute exactly the fields captured before approval. Confirmation cannot alter the proposal.
  const fields = proposal.args?.fields;
  if (!fields || typeof fields !== "object" || Array.isArray(fields)) {
    return res.status(400).json({ ok: false, error: "approved_fields_missing" });
  }

  const allowedFields = ["title", "content", "excerpt", "status", "slug"];
  const safeFields = Object.fromEntries(Object.entries(fields).filter(([key]) => allowedFields.includes(key)));
  if ("status" in safeFields && !["draft", "pending", "private", "publish"].includes(String(safeFields.status))) {
    return res.status(400).json({ ok: false, error: "invalid_status" });
  }
  if (Object.values(safeFields).some((value) => typeof value !== "string")) {
    return res.status(400).json({ ok: false, error: "field_values_must_be_strings" });
  }
  if (!Object.keys(safeFields).length) {
    return res.status(400).json({ ok: false, error: "no_allowed_fields" });
  }

  try {
    // Read-before-write: refuse to mutate a page we cannot verify immediately before execution.
    let before;
    try {
      before = await mcpClient.call("wordpress_get_page", { page_id: proposal.args.page_id });
    } catch (readError) {
      console.error("[JARVIS_APPROVED_WRITE_PREFLIGHT_ERROR]", proposal.args.page_id, readError.message);
      return res.status(502).json({ ok: false, approved: true, executed: false, error: "preflight_read_failed" });
    }

    const output = await mcpClient.call("wordpress_update_page", {
      page_id: proposal.args.page_id,
      fields_json: JSON.stringify(safeFields)
    }, { approved: true });

    // Verify-after-write: do not report success unless the page is readable after mutation.
    let after;
    try {
      after = await mcpClient.call("wordpress_get_page", { page_id: proposal.args.page_id });
    } catch (verifyError) {
      console.error("[JARVIS_APPROVED_WRITE_VERIFY_ERROR]", proposal.args.page_id, verifyError.message);
      return res.status(502).json({
        ok: false,
        approved: true,
        executed: true,
        verified: false,
        error: "post_write_verification_failed"
      });
    }
    const afterParsed = parseMaybeJson(after);
    const afterPage = afterParsed?.data || afterParsed?.structuredContent?.data || afterParsed;
    const mismatches = [];
    for (const [field, expected] of Object.entries(safeFields)) {
      let actual = afterPage?.[field];
      if (field === "title" && actual && typeof actual === "object") actual = actual.rendered ?? actual.raw;
      if (String(actual ?? "") !== String(expected)) mismatches.push({ field, expected, actual: actual ?? null });
    }
    if (mismatches.length) {
      console.error("[JARVIS_APPROVED_WRITE_VERIFY_MISMATCH]", proposal.args.page_id, JSON.stringify(mismatches));
      return res.status(502).json({ ok: false, approved: true, executed: true, verified: false, error: "post_write_value_mismatch", mismatches });
    }
    console.log("[JARVIS_APPROVED_WRITE]", proposal.action, proposal.args.page_id, Object.keys(safeFields));
    return res.json({
      ok: true,
      approved: true,
      executed: true,
      action: proposal.action,
      page_id: proposal.args.page_id,
      fields: safeFields,
      preflight_verified: Boolean(before),
      post_write_verified: true,
      result: parseMaybeJson(output)
    });
  } catch (error) {
    console.error("[JARVIS_APPROVED_WRITE_ERROR]", proposal.action, error.message);
    return res.status(502).json({ ok: false, approved: true, executed: false, error: error.message });
  }
});

function runApprovalSelfTest(source = "internal") {
  const approvalId = createApprovalProposal("approval_gate_test", { source });
  const proposal = consumeApprovalProposal(approvalId);
  const singleUse = consumeApprovalProposal(approvalId) === null;
  return { ok: Boolean(proposal && proposal.action === "approval_gate_test" && singleUse), mutation: false, single_use: singleUse };
}

app.get("/api/approval/test", (_req, res) => {
  const approvalId = createApprovalProposal("approval_gate_test", { source: "internal_get_test" });
  const proposal = consumeApprovalProposal(approvalId);
  const singleUse = consumeApprovalProposal(approvalId) === null;
  const ok = Boolean(proposal && proposal.action === "approval_gate_test" && singleUse);
  return res.status(ok ? 200 : 500).json({
    ok,
    mutation: false,
    single_use: singleUse,
    result: ok ? "Approval gate self-test passed without WordPress mutation." : "Approval gate self-test failed."
  });
});

app.post("/api/approval/test", (req, res) => {
  const approvalId = createApprovalProposal("approval_gate_test", { source: "internal_test" });
  const proposal = consumeApprovalProposal(approvalId);
  if (!proposal || proposal.action !== "approval_gate_test") {
    return res.status(500).json({ ok: false, error: "approval_gate_self_test_failed" });
  }
  return res.json({
    ok: true,
    mutation: false,
    single_use: consumeApprovalProposal(approvalId) === null,
    result: "Approval gate self-test passed without WordPress mutation."
  });
});

app.post("/api/approval/cancel", (req, res) => {
  const cancelled = cancelApprovalProposal(req.body?.approval_id);
  return res.json({ ok: true, cancelled });
});

function runDiagnosticGuardSelfTest() {
  const base = { car:"Тестовый автомобиль", mileage:"100000", vin:"WVWZZZ1JZXW000001", complaint:"Стук на неровностях", evidence:"При механической нагрузке воспроизведён люфт", finding:"Люфт стойки стабилизатора", urgency:"Планово", recommendation:"Заменить подтверждённо неисправную стойку и выполнить контроль", repairApproved:false };
  const check = (patch) => routeTranscriptTask("Создай диагностический PDF по текущей карте", { ...base, ...patch });
  const tests = {
    valid: check({})?.name === "generate_client_diagnostic_pdf",
    missing_evidence: Boolean(check({ evidence:"" })?.error),
    invalid_vin: Boolean(check({ vin:"INVALID" })?.error),
    invalid_mileage: Boolean(check({ mileage:"9999999" })?.error),
    repair_before_approval: Boolean(check({ repairResult:"Заменена стойка" })?.error),
    approval_without_amount: Boolean(check({ repairApproved:true, approvalRef:"звонок" })?.error),
    approval_without_reference: Boolean(check({ repairApproved:true, approvedAmount:"10000" })?.error),
    overrun: Boolean(check({ repairApproved:true, approvedAmount:"10000", approvalRef:"сообщение", laborAmount:"6000", partsAmount:"5000" })?.error),
    premature_close: Boolean(check({ finalCheck:true })?.error),
    complete_repair_cycle: check({ repairApproved:true, approvedAmount:"10000", approvalRef:"сообщение клиента", repairResult:"Заменена подтверждённо неисправная стойка", controlCheck:"Люфт и стук после ремонта отсутствуют", laborAmount:"3000", partsAmount:"5000", finalCheck:true })?.name === "generate_client_diagnostic_pdf"
  };
  return { ok:Object.values(tests).every(Boolean), mutation:false, tests };
}

const diagnosticGuardSelfTest = runDiagnosticGuardSelfTest();
console.log("[JARVIS_DIAGNOSTIC_GUARD_SELF_TEST]", JSON.stringify(diagnosticGuardSelfTest));

app.post("/api/diagnostic/validate", (req, res) => {
  const caseData = req.body?.case && typeof req.body.case === "object" && !Array.isArray(req.body.case) ? req.body.case : null;
  const task = routeTranscriptTask("Создай диагностический PDF по текущей карте", caseData);
  if (!task) return res.status(500).json({ ok: false, error: "validation_route_unavailable" });
  if (task.error) return res.status(422).json({ ok: false, error: task.error });
  if (task.name !== "generate_client_diagnostic_pdf") return res.status(500).json({ ok: false, error: "unexpected_validation_route" });
  return res.json({ ok: true, ready: true, report_name: task.args?.report_name || null });
});

app.post("/api/route-transcript", async (req, res) => {
  const origin = req.get("origin");
  const host = req.get("host");
  if (origin && origin !== `https://${host}`) {
    return res.status(403).json({ error: "Unexpected request origin" });
  }

  const text = String(req.body?.text || "").trim();
  const caseData = req.body?.case && typeof req.body.case === "object" && !Array.isArray(req.body.case) ? req.body.case : null;
  if (!text) {
    return res.status(400).json({ error: "Transcript text is required" });
  }

  const task = routeTranscriptTask(text, caseData);
  if (!task) {
    const normalized = normalizeTranscript(text);
    console.log("[JARVIS_ROUTE_UNMATCHED]", JSON.stringify({
      length: normalized.length,
      preview: normalized.slice(0, 160)
    }));
    return res.status(204).end();
  }

  console.log("[JARVIS_ROUTE_MATCHED]", task.name || task.action || "unknown");

  if (task.error) {
    return res.status(422).json({ ok: false, error: task.error });
  }

  if (task.approval_required) {
    const approvalId = createApprovalProposal(task.action, task.args);
    return res.json({
      ok: true,
      approval_required: true,
      approval_id: approvalId,
      expires_in_seconds: APPROVAL_TTL_MS / 1000,
      result: task.action === "wordpress_update_page"
        ? `Подготовлено изменение страницы ${task.args.page_id}: ${JSON.stringify(task.args.fields)}. Ничего не изменено. Для выполнения подтвердите: ${approvalId}`
        : `Действие изменяет данные и не выполнено. Для продолжения требуется подтверждение: ${approvalId}`
    });
  }

  try {
    const output = await executeTool(task.name, task.args);
    console.log("[JARVIS_BROWSER_TRANSCRIPT_ROUTE]", task.name, text);
    console.log("[JARVIS_BROWSER_TRANSCRIPT_RESULT]", task.name);
    const pdfResource = task.name === "generate_client_diagnostic_pdf" ? extractPdfResource(output) : null;
    if (task.name === "generate_client_diagnostic_pdf") console.log("[JARVIS_PDF_RESOURCE]", pdfResource ? "found" : "missing", typeof output);
    return res.json({
      ok: true,
      tool: task.name,
      result: pdfResource || formatBrowserToolResult(task, output, text)
    });
  } catch (error) {
    console.error("[JARVIS_BROWSER_TRANSCRIPT_ERROR]", task.name, error.message);
    return res.status(502).json({
      ok: false,
      tool: task.name,
      error: error.message
    });
  }
});

app.post("/api/diagnostic/export", async (req, res) => {
  const origin = req.get("origin");
  const host = req.get("host");
  if (origin && origin !== `https://${host}`) return res.status(403).json({ error: "Unexpected request origin" });
  const caseData = req.body?.case && typeof req.body.case === "object" && !Array.isArray(req.body.case) ? req.body.case : null;
  if (!caseData) return res.status(400).json({ ok: false, error: "Diagnostic case is required" });
  const diagnostic = Object.fromEntries(Array.from({ length: 12 }, (_, i) => {
    const n = i + 1;
    return ["p" + n, { result: String(caseData["diagnostic_p" + n + "_result"] || "").trim(), evidence: String(caseData["diagnostic_p" + n + "_evidence"] || "").trim() }];
  }));
  const populatedPoints = Object.values(diagnostic).filter((p) => p.result && p.evidence).length;
  const repairApproved = caseData.repairApproved === true || String(caseData.repairApproved || "").toLowerCase() === "true";
  const finalCheck = caseData.finalCheck === true || String(caseData.finalCheck || "").toLowerCase() === "true";
  const hasFinding = Boolean(String(caseData.finding || "").trim() && String(caseData.evidence || "").trim());
  const hasRepair = Boolean(String(caseData.repairResult || "").trim());
  const hasControl = Boolean(String(caseData.controlCheck || "").trim());
  const handedOver = Boolean(String(caseData.clientHandover || "").trim());
  if ((hasRepair || hasControl || finalCheck) && !repairApproved) return res.status(409).json({ ok: false, error: "repair_approval_required" });
  if (finalCheck && (!hasRepair || !hasControl)) return res.status(409).json({ ok: false, error: "repair_control_required" });
  if (repairApproved && (!String(caseData.approvedAmount || "").trim() || !String(caseData.approvalRef || "").trim())) return res.status(409).json({ ok: false, error: "approval_evidence_required" });
  let workflowStatus = populatedPoints < 12 ? "Диагностика" : hasFinding ? "Неисправность доказана" : "Диагностика завершена";
  if (hasFinding && !repairApproved) workflowStatus = "Ожидает согласования";
  if (repairApproved && !hasRepair) workflowStatus = "В ремонте";
  if (repairApproved && hasRepair && !hasControl) workflowStatus = "Контроль";
  if (repairApproved && hasRepair && hasControl && finalCheck) workflowStatus = handedOver ? "Выдано" : "Готово";
  const archiveId = String(caseData.orderNumber || ("JARVIS-" + Date.now())).trim();
  const clientMessageDraft = hasFinding
    ? ("Автохирург: по автомобилю " + String(caseData.car || "").trim() + " подтверждено: " + String(caseData.finding || "").trim() + ". Доказательство: " + String(caseData.evidence || "").trim() + ". Рекомендация: " + String(caseData.recommendation || "").trim() + ". Статус: " + workflowStatus + ".")
    : ("Автохирург: диагностика автомобиля " + String(caseData.car || "").trim() + " выполнена. Статус: " + workflowStatus + ".");
  const seoCaseDraft = {
    title: String(caseData.car || "Автомобиль").trim() + ": " + String(caseData.complaint || "диагностический кейс").trim(),
    question: String(caseData.complaint || "").trim(),
    short_answer: hasFinding ? ("Подтверждено: " + String(caseData.finding || "").trim()) : "Диагностика завершена без публикации неподтверждённых выводов.",
    symptoms: String(caseData.complaint || "").trim(),
    proof: String(caseData.evidence || "").trim(),
    repair: String(caseData.repairResult || caseData.recommendation || "").trim(),
    publish_ready: Boolean(finalCheck && hasFinding && populatedPoints === 12),
    requires_human_review: true
  };
  const exported = {
    ok: true,
    schema: "avtohirurg.diagnostic.v1",
    exported_at: new Date().toISOString(),
    archive: { id: archiveId, status: workflowStatus, diagnostic_points: populatedPoints, media_url: String(caseData.mediaUrl || "").trim() },
    analytics: { diagnostic_complete: populatedPoints === 12, fault_confirmed: hasFinding, repair_approved: repairApproved, repair_completed: hasRepair, control_completed: hasControl, final_check: finalCheck, handed_over: handedOver },
    client_message: { draft: clientMessageDraft, requires_human_approval: true, sent: false },
    seo_case: seoCaseDraft,
    case: { ...caseData, diagnostic, workflowStatus }
  };
  if (db) {
    try {
      await db.query(`INSERT INTO jarvis_cases
        (id,vin,plate,car,mileage,status,complaint,finding,evidence,recommendation,approved_amount,approval_ref,repair_result,control_check,media_url,next_service,warranty,client_handover,payload,updated_at)
        VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18,$19,now())
        ON CONFLICT (id) DO UPDATE SET vin=EXCLUDED.vin,plate=EXCLUDED.plate,car=EXCLUDED.car,mileage=EXCLUDED.mileage,status=EXCLUDED.status,
        complaint=EXCLUDED.complaint,finding=EXCLUDED.finding,evidence=EXCLUDED.evidence,recommendation=EXCLUDED.recommendation,
        approved_amount=EXCLUDED.approved_amount,approval_ref=EXCLUDED.approval_ref,repair_result=EXCLUDED.repair_result,
        control_check=EXCLUDED.control_check,media_url=EXCLUDED.media_url,next_service=EXCLUDED.next_service,warranty=EXCLUDED.warranty,
        client_handover=EXCLUDED.client_handover,payload=EXCLUDED.payload,updated_at=now()`,
        [archiveId,String(caseData.vin||""),String(caseData.plate||""),String(caseData.car||""),String(caseData.mileage||""),workflowStatus,
         String(caseData.complaint||""),String(caseData.finding||""),String(caseData.evidence||""),String(caseData.recommendation||""),
         String(caseData.approvedAmount||""),String(caseData.approvalRef||""),String(caseData.repairResult||""),String(caseData.controlCheck||""),
         String(caseData.mediaUrl||""),String(caseData.nextService||""),String(caseData.warranty||""),String(caseData.clientHandover||""),JSON.stringify(exported)]);
      if (String(caseData.nextService || "").trim()) {
        const exists = await db.query("SELECT 1 FROM jarvis_followups WHERE case_id=$1 AND reason=$2 LIMIT 1",[archiveId,String(caseData.nextService).trim()]);
        if (!exists.rowCount) await db.query("INSERT INTO jarvis_followups(case_id,reason) VALUES($1,$2)",[archiveId,String(caseData.nextService).trim()]);
      }
    } catch (e) { console.error("[OPS_DB_SAVE]", e.message); }
  }
  const webhookUrl = String(process.env.N8N_DIAGNOSTIC_WEBHOOK_URL || "").trim();
  const webhookToken = String(process.env.DIAGNOSTIC_WEBHOOK_TOKEN || "").trim();
  if (!webhookToken) return res.json({ ...exported, automation: { configured: true, delivered: false, error: "auth_not_configured" } });
  if (!webhookUrl) return res.json({ ...exported, automation: { configured: false, delivered: false } });
  try {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 5000);
    const response = await fetch(webhookUrl, { method: "POST", headers: { "content-type": "application/json", "x-avtohirurg-token": String(process.env.DIAGNOSTIC_WEBHOOK_TOKEN || "") }, body: JSON.stringify(exported), signal: controller.signal });
    clearTimeout(timer);
    let pdf = { generated: false };
    if (response.ok && populatedPoints === 12 && finalCheck) {
      try {
        const pdfTask = routeTranscriptTask("Сформируй диагностический PDF", { ...caseData, diagnostic });
        if (pdfTask?.name === "generate_client_diagnostic_pdf") {
          const pdfOutput = await executeTool(pdfTask.name, pdfTask.args);
          const pdfResource = extractPdfResource(pdfOutput);
          pdf = { generated: Boolean(pdfResource), resource: pdfResource || null };
        }
      } catch (pdfError) {
        pdf = { generated: false, error: "pdf_generation_failed" };
      }
    }
    return res.json({ ...exported, automation: { configured: true, delivered: response.ok, status: response.status }, pdf });
  } catch (error) {
    return res.json({ ...exported, automation: { configured: true, delivered: false, error: error.name === "AbortError" ? "timeout" : "delivery_failed" } });
  }
});

app.get("/api/diagnostic/pdf-self-test", async (_req, res) => {
  const diagnostic = Object.fromEntries(Array.from({ length: 12 }, (_, i) => ["p" + (i + 1), {
    result: i === 6 ? "Выявлен люфт правой передней стойки стабилизатора" : "Проверено, отклонений не зафиксировано",
    evidence: i === 6 ? "Люфт подтверждён механической нагрузкой" : "Контроль по протоколу Автохирурга"
  }]));
  const caseData = {
    car: "Volkswagen Tiguan",
    plate: "А123АА69",
    vin: "WVGZZZ5NZJW000001",
    mileage: "128450",
    complaint: "Стук в передней подвеске на неровностях",
    evidence: "Механическая нагрузка воспроизвела характерный стук",
    finding: "Люфт правой передней стойки стабилизатора",
    urgency: "Плановый ремонт",
    recommendation: "Заменить подтверждённо неисправную стойку стабилизатора",
    diagnostic
  };
  const task = routeTranscriptTask("Сформируй диагностический PDF", caseData);
  if (!task?.name) return res.status(500).json({ ok: false, error: task?.error || "PDF route not created" });
  try {
    const output = await executeTool(task.name, task.args);
    const pdf = extractPdfResource(output);
    const parsedData = JSON.parse(task.args.data_json);
    const populated = Object.values(parsedData.diagnostic || {}).filter((p) => p?.result && p.result !== "Не зафиксировано").length;
    return res.json({ ok: Boolean(pdf), tool: task.name, diagnostic_points: Object.keys(parsedData.diagnostic || {}).length, populated_points: populated, pdf_resource: Boolean(pdf) });
  } catch (error) {
    return res.status(500).json({ ok: false, error: error.message });
  }
});


app.get("/api/ops/cases", async (req,res) => {
  if (!db) return res.status(503).json({ok:false,error:"database_not_configured"});
  const status=String(req.query.status||"").trim();
  const q=status ? await db.query("SELECT id,car,plate,vin,mileage,status,complaint,finding,next_service,warranty,updated_at FROM jarvis_cases WHERE status=$1 ORDER BY updated_at DESC LIMIT 200",[status])
                 : await db.query("SELECT id,car,plate,vin,mileage,status,complaint,finding,next_service,warranty,updated_at FROM jarvis_cases ORDER BY updated_at DESC LIMIT 200");
  res.json({ok:true,cases:q.rows});
});
app.get("/api/ops/vehicle", async (req,res) => {
  if (!db) return res.status(503).json({ok:false,error:"database_not_configured"});
  const key=String(req.query.q||"").trim(); if(!key) return res.status(400).json({ok:false,error:"query_required"});
  const q=await db.query("SELECT * FROM jarvis_cases WHERE vin=$1 OR plate=$1 ORDER BY updated_at DESC LIMIT 50",[key]);
  res.json({ok:true,visits:q.rows});
});
app.post("/api/ops/parts", async (req,res) => {
  if (!db) return res.status(503).json({ok:false,error:"database_not_configured"});
  const b=req.body||{}; if(!b.case_id||!b.part_name) return res.status(400).json({ok:false,error:"case_id_and_part_name_required"});
  const q=await db.query("INSERT INTO jarvis_parts(case_id,part_name,availability,supplier,price,eta) VALUES($1,$2,$3,$4,$5,$6) RETURNING *",
    [String(b.case_id),String(b.part_name),String(b.availability||"unknown"),String(b.supplier||""),Number(b.price||0),String(b.eta||"")]);
  res.json({ok:true,part:q.rows[0]});
});
app.delete("/api/ops/test-data/:id", async (req,res) => {
  if (!db) return res.status(503).json({ok:false,error:"database_not_configured"});
  const id=String(req.params.id||""); if(!id.startsWith("TEST-")) return res.status(403).json({ok:false,error:"test_records_only"});
  await db.query("DELETE FROM jarvis_cases WHERE id=$1",[id]); res.json({ok:true,deleted:id});
});
app.get("/api/ops/dashboard", async (_req,res) => {
  if (!db) return res.status(503).json({ok:false,error:"database_not_configured"});
  const by=await db.query("SELECT status,count(*)::int count FROM jarvis_cases GROUP BY status ORDER BY status");
  const k=await db.query(`SELECT count(*)::int total,
    count(*) FILTER (WHERE finding<>'')::int faults,
    count(*) FILTER (WHERE approval_ref<>'')::int approved,
    count(*) FILTER (WHERE repair_result<>'')::int repaired,
    count(*) FILTER (WHERE client_handover<>'')::int handed_over
    FROM jarvis_cases`);
  const follow=await db.query("SELECT count(*)::int planned FROM jarvis_followups WHERE status='planned'");
  res.json({ok:true,kpi:k.rows[0],by_status:by.rows,followups:follow.rows[0].planned});
});

app.get("/health", (_req, res) =>
  res.json({
    ok: true,
    service: "avtohirurg-jarvis-voice",
    core_loaded: true,
    mcp_configured: mcpClient.configured,
    mcp_read_tools: MCP_READ_TOOLS,
    delegated_tools: buildDelegatedTools().map((tool) => tool.name),
    approval_write_tools: MCP_APPROVAL_TOOLS,
    approval_gate: true,
    approval_self_test: "GET /api/approval/test",
    approval_ttl_seconds: APPROVAL_TTL_MS / 1000,
    pending_approvals: pendingApprovals.size,
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
            `\  if (task?.validation_error) return res.status(400).json({ ok:false, error:"case_validation_failed", result:task.message });
n
Голосовой runtime: говори кратко и естественно.

Delegation policy:
- Делегируй backend задачу, если пользователь просит проверить WordPress, сайт, страницу или авторизацию.
- Делегируй backend задачу, если пользователь просит диагностику автомобиля, 12-пунктный протокол или проверку симптома.
- Если пользователь просит сформировать, создать или подготовить диагностическое заключение/PDF/отчёт, ОБЯЗАТЕЛЬНО делегируй generate_client_diagnostic_pdf до голосового ответа. Не заменяй вызов инструмента устным описанием.
- Делегируй backend задачу, если ответ требует фактической проверки через MCP.
- Делегируй ДО ответа, зависящего от backend. Не угадывай результат и не говори «проверено/готово», пока backend не вернул результат.
- Если backend недоступен или вернул ошибку, сообщи об этом прямо.
Backend capabilities:
  * Проверка WordPress: состояние REST API, текущий пользователь, чтение страницы.
  * Автодиагностика: предварительный анализ симптома, срочность, 12-пунктный протокол, протокол Автохирурга, клиентское заключение.
  * Чек-лист Автохирурга.
  * Клиентский PDF: боевой шаблон Carbone V2 через generate_client_diagnostic_pdf.
MANDATORY examples:
  * «проверь состояние WordPress» / «проверь сайт» → delegate to wordpress_health.
  * «проверь авторизацию WordPress» → delegate to wordpress_current_user.
  * «проверь страницу WordPress» → delegate to wordpress_get_page when page ID is known; otherwise ask for the ID.
  * «запусти 12-пунктную диагностику» → delegate to diagnostic_12_points.
  * «разбери симптом» / «проведи диагностику» → delegate to diagnose_symptom.
  * «сформируй диагностическое заключение», «сделай PDF диагностики», «подготовь отчёт по диагностике» → delegate to generate_client_diagnostic_pdf. Если пользователь явно просит тестовый документ и не дал реальные данные, разрешено заполнить безопасные тестовые данные; не выдавай их за реальные данные клиента.
For these requests, do not answer from general knowledge and do not ask the user to perform the check themselves unless the backend reports an error.
Backend tools: wordpress_health, wordpress_current_user, wordpress_get_page, diagnose, diagnose_symptom, repair_urgency, avtohirurg_protocol, diagnostic_12_points, client_conclusion, checklist, generate_client_diagnostic_pdf.
Для диагностики сначала используй диагностические инструменты. Для WordPress используй read-only инструменты. Любое изменение сайта, данных или настроек требует явного подтверждения владельца до выполнения.`,
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
const startupApprovalTest = runApprovalSelfTest("startup");
console.log("[JARVIS_APPROVAL_SELF_TEST]", JSON.stringify(startupApprovalTest));
