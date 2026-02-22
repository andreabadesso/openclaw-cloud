import crypto from "node:crypto";
import { stream as piStream } from "@mariozechner/pi-ai";
import { config } from "./config.js";

/**
 * Handle an LLM proxy request using pi-ai.
 *
 * Accepts OpenAI Chat Completions format from the gateway,
 * uses pi-ai to call the real upstream (any provider), and
 * returns OpenAI Chat Completions format back.
 *
 * @param {Buffer} body - Raw request body (OpenAI chat completions format)
 * @param {import("http").ServerResponse} res
 * @param {{warning: boolean}} limitResult
 * @returns {Promise<{prompt_tokens: number, completion_tokens: number, model: string, request_id: string}>}
 */
export async function forwardRequest(body, res, limitResult) {
  const reqBody = JSON.parse(body);
  const isStreaming = reqBody.stream === true;

  // Convert OpenAI messages to pi-ai context format
  const context = openAiToContext(reqBody);
  const requestId = `chatcmpl-${crypto.randomUUID().replace(/-/g, "").slice(0, 24)}`;


  if (limitResult.warning) {
    res.setHeader("X-Token-Warning", "90%");
  }

  if (isStreaming) {
    return handleStreaming(context, res, requestId);
  } else {
    return handleNonStreaming(context, res, requestId);
  }
}

/**
 * Convert OpenAI Chat Completions messages to pi-ai context.
 * OpenAI: { messages: [{ role, content }], system?, ... }
 * pi-ai:  { messages: [{ role, content: ContentBlock[] }], systemPrompt? }
 */
function openAiToContext(reqBody) {
  const ctx = { messages: [] };

  for (const msg of reqBody.messages || []) {
    if (msg.role === "system" || msg.role === "developer") {
      // pi-ai uses systemPrompt for system/developer messages
      const text = typeof msg.content === "string" ? msg.content : msg.content?.map((b) => b.text || "").join("");
      ctx.systemPrompt = ctx.systemPrompt ? ctx.systemPrompt + "\n" + text : text;
      continue;
    }

    const content = [];
    if (typeof msg.content === "string") {
      content.push({ type: "text", text: msg.content });
    } else if (Array.isArray(msg.content)) {
      for (const part of msg.content) {
        if (part.type === "text") {
          content.push({ type: "text", text: part.text });
        } else if (part.type === "image_url") {
          content.push({ type: "image", url: part.image_url?.url || "" });
        }
      }
    }

    ctx.messages.push({ role: msg.role, content });
  }

  return ctx;
}

async function handleNonStreaming(context, res, requestId) {
  const usage = { prompt_tokens: 0, completion_tokens: 0, model: config.model.id, request_id: requestId };
  let fullText = "";

  try {
    const eventStream = piStream(config.model, context, { apiKey: config.apiKey });
    for await (const event of eventStream) {
      if (event.type === "text_delta") {
        fullText += event.delta;
      } else if (event.type === "done") {
        if (event.message?.usage) {
          usage.prompt_tokens = event.message.usage.input || 0;
          usage.completion_tokens = event.message.usage.output || 0;
        }
        usage.model = event.message?.model || config.model.id;
      } else if (event.type === "error") {
        throw new Error(typeof event.error === "string" ? event.error : event.error?.message || "Upstream error");
      }
    }
  } catch (err) {
    if (!res.headersSent) {
      res.writeHead(502, { "content-type": "application/json" });
      res.end(JSON.stringify({ error: { message: err.message, type: "upstream_error" } }));
    }
    return usage;
  }

  const response = {
    id: requestId,
    object: "chat.completion",
    created: Math.floor(Date.now() / 1000),
    model: usage.model,
    choices: [{ index: 0, message: { role: "assistant", content: fullText }, finish_reason: "stop" }],
    usage: { prompt_tokens: usage.prompt_tokens, completion_tokens: usage.completion_tokens, total_tokens: usage.prompt_tokens + usage.completion_tokens },
  };

  res.writeHead(200, { "content-type": "application/json" });
  res.end(JSON.stringify(response));
  return usage;
}

async function handleStreaming(context, res, requestId) {
  const usage = { prompt_tokens: 0, completion_tokens: 0, model: config.model.id, request_id: requestId };

  res.writeHead(200, {
    "content-type": "text/event-stream",
    "cache-control": "no-cache",
    connection: "keep-alive",
    "x-accel-buffering": "no",
  });

  try {
    const eventStream = piStream(config.model, context, { apiKey: config.apiKey });

    for await (const event of eventStream) {
      if (event.type === "text_delta") {
        const chunk = {
          id: requestId,
          object: "chat.completion.chunk",
          created: Math.floor(Date.now() / 1000),
          model: usage.model,
          choices: [{ index: 0, delta: { content: event.delta }, finish_reason: null }],
        };
        res.write(`data: ${JSON.stringify(chunk)}\n\n`);
      } else if (event.type === "done") {
        if (event.message?.usage) {
          usage.prompt_tokens = event.message.usage.input || 0;
          usage.completion_tokens = event.message.usage.output || 0;
        }
        usage.model = event.message?.model || config.model.id;

        // Send final chunk with finish_reason and usage
        const finalChunk = {
          id: requestId,
          object: "chat.completion.chunk",
          created: Math.floor(Date.now() / 1000),
          model: usage.model,
          choices: [{ index: 0, delta: {}, finish_reason: "stop" }],
          usage: { prompt_tokens: usage.prompt_tokens, completion_tokens: usage.completion_tokens, total_tokens: usage.prompt_tokens + usage.completion_tokens },
        };
        res.write(`data: ${JSON.stringify(finalChunk)}\n\n`);
        res.write("data: [DONE]\n\n");
      } else if (event.type === "error") {
        const errMsg = typeof event.error === "string" ? event.error : event.error?.message || "Upstream error";
        const errChunk = {
          id: requestId,
          object: "chat.completion.chunk",
          created: Math.floor(Date.now() / 1000),
          model: usage.model,
          choices: [{ index: 0, delta: {}, finish_reason: "stop" }],
        };
        res.write(`data: ${JSON.stringify(errChunk)}\n\n`);
        res.write("data: [DONE]\n\n");
        console.error("Upstream stream error:", errMsg);
      }
    }
  } catch (err) {
    console.error("Stream error:", err);
    if (!res.headersSent) {
      res.writeHead(502, { "content-type": "application/json" });
      res.end(JSON.stringify({ error: { message: err.message, type: "upstream_error" } }));
    }
  }

  res.end();
  return usage;
}
