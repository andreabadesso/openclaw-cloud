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
 * Convert OpenAI Chat Completions request to pi-ai context.
 *
 * Handles: system messages, user/assistant text+image, tool definitions,
 * assistant tool_calls, and tool result messages.
 */
function openAiToContext(reqBody) {
  const ctx = { messages: [] };

  // Convert tools: OpenAI { type: "function", function: { name, description, parameters } }
  // → pi-ai { name, description, parameters }
  if (Array.isArray(reqBody.tools) && reqBody.tools.length > 0) {
    ctx.tools = reqBody.tools
      .filter((t) => t.type === "function" && t.function)
      .map((t) => ({
        name: t.function.name,
        description: t.function.description || "",
        parameters: t.function.parameters || {},
      }));
  }

  for (const msg of reqBody.messages || []) {
    if (msg.role === "system" || msg.role === "developer") {
      const text = typeof msg.content === "string" ? msg.content : msg.content?.map((b) => b.text || "").join("");
      ctx.systemPrompt = ctx.systemPrompt ? ctx.systemPrompt + "\n" + text : text;
      continue;
    }

    if (msg.role === "tool") {
      // OpenAI tool result → pi-ai ToolResultMessage
      ctx.messages.push({
        role: "toolResult",
        toolCallId: msg.tool_call_id || "",
        toolName: msg.name || "",
        content: [{ type: "text", text: typeof msg.content === "string" ? msg.content : JSON.stringify(msg.content) }],
        isError: false,
        timestamp: Date.now(),
      });
      continue;
    }

    if (msg.role === "assistant") {
      const content = [];

      // Text content
      if (typeof msg.content === "string" && msg.content) {
        content.push({ type: "text", text: msg.content });
      } else if (Array.isArray(msg.content)) {
        for (const part of msg.content) {
          if (part.type === "text") {
            content.push({ type: "text", text: part.text });
          }
        }
      }

      // Tool calls in assistant message
      if (Array.isArray(msg.tool_calls)) {
        for (const tc of msg.tool_calls) {
          let args = {};
          if (typeof tc.function?.arguments === "string") {
            try { args = JSON.parse(tc.function.arguments); } catch { args = {}; }
          } else if (tc.function?.arguments) {
            args = tc.function.arguments;
          }
          content.push({
            type: "toolCall",
            id: tc.id || "",
            name: tc.function?.name || "",
            arguments: args,
          });
        }
      }

      ctx.messages.push({ role: "assistant", content });
      continue;
    }

    // User messages
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

/**
 * Convert pi-ai AssistantMessage content to OpenAI response message.
 */
function piMessageToOpenAi(message) {
  let textContent = "";
  const toolCalls = [];

  for (const block of message.content || []) {
    if (block.type === "text") {
      textContent += block.text;
    } else if (block.type === "toolCall") {
      toolCalls.push({
        id: block.id,
        type: "function",
        function: {
          name: block.name,
          arguments: JSON.stringify(block.arguments),
        },
      });
    }
    // thinking blocks are omitted from the OpenAI response
  }

  const result = { role: "assistant", content: textContent || null };
  if (toolCalls.length > 0) {
    result.tool_calls = toolCalls;
  }
  return result;
}

/**
 * Map pi-ai stop reason to OpenAI finish_reason.
 */
function mapFinishReason(reason) {
  if (reason === "toolUse") return "tool_calls";
  if (reason === "length") return "length";
  return "stop";
}

async function handleNonStreaming(context, res, requestId) {
  const usage = { prompt_tokens: 0, completion_tokens: 0, model: config.model.id, request_id: requestId };

  try {
    const eventStream = piStream(config.model, context, { apiKey: config.apiKey });
    let doneMessage = null;
    let doneReason = "stop";

    for await (const event of eventStream) {
      if (event.type === "done") {
        doneMessage = event.message;
        doneReason = event.reason;
        if (event.message?.usage) {
          usage.prompt_tokens = event.message.usage.input || 0;
          usage.completion_tokens = event.message.usage.output || 0;
        }
        usage.model = event.message?.model || config.model.id;
      } else if (event.type === "error") {
        throw new Error(typeof event.error === "string" ? event.error : event.error?.message || "Upstream error");
      }
    }

    const openAiMessage = doneMessage ? piMessageToOpenAi(doneMessage) : { role: "assistant", content: "" };
    const finishReason = mapFinishReason(doneReason);

    const response = {
      id: requestId,
      object: "chat.completion",
      created: Math.floor(Date.now() / 1000),
      model: usage.model,
      choices: [{ index: 0, message: openAiMessage, finish_reason: finishReason }],
      usage: { prompt_tokens: usage.prompt_tokens, completion_tokens: usage.completion_tokens, total_tokens: usage.prompt_tokens + usage.completion_tokens },
    };

    res.writeHead(200, { "content-type": "application/json" });
    res.end(JSON.stringify(response));
  } catch (err) {
    if (!res.headersSent) {
      res.writeHead(502, { "content-type": "application/json" });
      res.end(JSON.stringify({ error: { message: err.message, type: "upstream_error" } }));
    }
  }

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

  // Track tool call indices for streaming (content array may mix text + tool calls)
  let toolCallStreamIndex = -1;
  const contentIndexToToolIndex = {};

  function writeChunk(data) {
    res.write(`data: ${JSON.stringify(data)}\n\n`);
  }

  try {
    const eventStream = piStream(config.model, context, { apiKey: config.apiKey });

    for await (const event of eventStream) {
      if (event.type === "text_delta") {
        writeChunk({
          id: requestId,
          object: "chat.completion.chunk",
          created: Math.floor(Date.now() / 1000),
          model: usage.model,
          choices: [{ index: 0, delta: { content: event.delta }, finish_reason: null }],
        });
      } else if (event.type === "toolcall_start") {
        toolCallStreamIndex++;
        contentIndexToToolIndex[event.contentIndex] = toolCallStreamIndex;

        // Extract id and name from partial content
        const partial = event.partial?.content?.[event.contentIndex];
        writeChunk({
          id: requestId,
          object: "chat.completion.chunk",
          created: Math.floor(Date.now() / 1000),
          model: usage.model,
          choices: [{
            index: 0,
            delta: {
              tool_calls: [{
                index: toolCallStreamIndex,
                id: partial?.id || `call_${crypto.randomUUID().replace(/-/g, "").slice(0, 24)}`,
                type: "function",
                function: { name: partial?.name || "", arguments: "" },
              }],
            },
            finish_reason: null,
          }],
        });
      } else if (event.type === "toolcall_delta") {
        const idx = contentIndexToToolIndex[event.contentIndex] ?? toolCallStreamIndex;
        writeChunk({
          id: requestId,
          object: "chat.completion.chunk",
          created: Math.floor(Date.now() / 1000),
          model: usage.model,
          choices: [{
            index: 0,
            delta: {
              tool_calls: [{
                index: idx,
                function: { arguments: event.delta },
              }],
            },
            finish_reason: null,
          }],
        });
      } else if (event.type === "done") {
        if (event.message?.usage) {
          usage.prompt_tokens = event.message.usage.input || 0;
          usage.completion_tokens = event.message.usage.output || 0;
        }
        usage.model = event.message?.model || config.model.id;

        const finishReason = mapFinishReason(event.reason);
        writeChunk({
          id: requestId,
          object: "chat.completion.chunk",
          created: Math.floor(Date.now() / 1000),
          model: usage.model,
          choices: [{ index: 0, delta: {}, finish_reason: finishReason }],
          usage: { prompt_tokens: usage.prompt_tokens, completion_tokens: usage.completion_tokens, total_tokens: usage.prompt_tokens + usage.completion_tokens },
        });
        res.write("data: [DONE]\n\n");
      } else if (event.type === "error") {
        const errMsg = typeof event.error === "string" ? event.error : event.error?.message || "Upstream error";
        writeChunk({
          id: requestId,
          object: "chat.completion.chunk",
          created: Math.floor(Date.now() / 1000),
          model: usage.model,
          choices: [{ index: 0, delta: {}, finish_reason: "stop" }],
        });
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
