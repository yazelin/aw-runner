export interface Env {
  RUNNER_KV: KVNamespace;
  RUNNER_API_KEY: string;
  TELEGRAM_BOT_TOKEN: string;
}

interface TelegramUpdate {
  message?: {
    chat: { id: number };
    text?: string;
  };
}

export default {
  async fetch(request: Request, env: Env, ctx: ExecutionContext): Promise<Response> {
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

    const runnerUrl = await env.RUNNER_KV.get("runner_url");
    if (!runnerUrl) {
      return new Response("Runner not available", { status: 503 });
    }

    const chat_id = String(message.chat.id);
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
