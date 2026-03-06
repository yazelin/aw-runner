export interface Env {
  RUNNER_KV: KVNamespace;
  RUNNER_API_KEY: string;
  TELEGRAM_BOT_TOKEN: string;
  ALLOWED_CHAT_ID: string;
}

interface TelegramUpdate {
  message?: {
    chat: { id: number };
    text?: string;
  };
}

export default {
  async fetch(request: Request, env: Env, ctx: ExecutionContext): Promise<Response> {
    const url = new URL(request.url);

    const corsHeaders = {
      "Access-Control-Allow-Origin": "*",
      "Access-Control-Allow-Methods": "GET, OPTIONS",
    };

    if (request.method === "OPTIONS") {
      return new Response(null, { status: 204, headers: corsHeaders });
    }

    // GET /status — proxy to FastAPI /status
    if (request.method === "GET" && url.pathname === "/status") {
      const runnerUrl = await env.RUNNER_KV.get("runner_url");
      if (!runnerUrl) {
        return Response.json({ status: "offline", runner_url: null }, { status: 503, headers: corsHeaders });
      }
      try {
        const res = await fetch(`${runnerUrl}/status`, { signal: AbortSignal.timeout(5000) });
        const data = await res.json();
        return Response.json({ ...data as object, runner_url: runnerUrl }, { headers: corsHeaders });
      } catch {
        return Response.json({ status: "unreachable", runner_url: runnerUrl }, { status: 503, headers: corsHeaders });
      }
    }

    if (request.method !== "POST") {
      return new Response("Method Not Allowed", { status: 405 });
    }

    let update: TelegramUpdate;
    try {
      update = await request.json();
    } catch {
      return new Response("Bad Request", { status: 400 });
    }

    const message = update.message;
    if (!message?.text) {
      return new Response("OK", { status: 200 });
    }

    // 只允許白名單 chat_id
    const chat_id = String(message.chat.id);
    if (chat_id !== env.ALLOWED_CHAT_ID) {
      return new Response("OK", { status: 200 }); // 靜默忽略，不回覆
    }

    const runnerUrl = await env.RUNNER_KV.get("runner_url");
    if (!runnerUrl) {
      return new Response("Runner not available", { status: 503 });
    }

    const text = message.text;

    ctx.waitUntil(
      fetch(`${runnerUrl}/task`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "x-api-key": env.RUNNER_API_KEY,
        },
        body: JSON.stringify({ text, chat_id }),
      })
    );

    return new Response("OK", { status: 200 });
  },
} satisfies ExportedHandler<Env>;
