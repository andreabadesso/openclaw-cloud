import { describe, it, expect, vi, beforeEach } from "vitest";

// Mock pi-ai stream
vi.mock("@mariozechner/pi-ai", () => ({
  stream: vi.fn(),
}));

// Mock config
vi.mock("../src/config.js", () => ({
  config: {
    apiKey: "test-api-key",
    model: { id: "test-model", api: "openai", baseUrl: "http://localhost" },
  },
}));

import { stream as piStream } from "@mariozechner/pi-ai";
import { forwardRequest } from "../src/proxy.js";

function makeRes() {
  const res = {
    headersSent: false,
    statusCode: null,
    headers: {},
    body: "",
    chunks: [],
    writeHead: vi.fn((status, headers) => {
      res.statusCode = status;
      res.headers = { ...res.headers, ...headers };
    }),
    setHeader: vi.fn((k, v) => {
      res.headers[k] = v;
    }),
    write: vi.fn((chunk) => {
      res.chunks.push(chunk);
    }),
    end: vi.fn((data) => {
      if (data) res.body = data;
      res.headersSent = true;
    }),
  };
  return res;
}

async function* makeEventStream(events) {
  for (const event of events) {
    yield event;
  }
}

describe("forwardRequest", () => {
  let res;

  beforeEach(() => {
    res = makeRes();
    vi.clearAllMocks();
  });

  describe("non-streaming", () => {
    it("returns OpenAI chat completion format", async () => {
      piStream.mockReturnValue(makeEventStream([
        { type: "text_delta", delta: "Hello " },
        { type: "text_delta", delta: "World" },
        { type: "done", reason: "stop", message: {
          content: [{ type: "text", text: "Hello World" }],
          usage: { input: 10, output: 5 },
          model: "gpt-4o",
        }},
      ]));

      const body = Buffer.from(JSON.stringify({
        model: "gpt-4o",
        messages: [{ role: "user", content: "Hi" }],
      }));

      const usage = await forwardRequest(body, res, { warning: false });

      expect(res.writeHead).toHaveBeenCalledWith(200, { "content-type": "application/json" });
      const responseBody = JSON.parse(res.end.mock.calls[0][0]);
      expect(responseBody.object).toBe("chat.completion");
      expect(responseBody.choices[0].message.content).toBe("Hello World");
      expect(responseBody.choices[0].finish_reason).toBe("stop");
      expect(responseBody.usage.prompt_tokens).toBe(10);
      expect(responseBody.usage.completion_tokens).toBe(5);
      expect(responseBody.usage.total_tokens).toBe(15);
      expect(usage.prompt_tokens).toBe(10);
      expect(usage.completion_tokens).toBe(5);
    });

    it("handles upstream error", async () => {
      piStream.mockReturnValue(makeEventStream([
        { type: "error", error: { message: "API overloaded" } },
      ]));

      const body = Buffer.from(JSON.stringify({
        messages: [{ role: "user", content: "Hi" }],
      }));

      const usage = await forwardRequest(body, res, { warning: false });

      expect(res.writeHead).toHaveBeenCalledWith(502, { "content-type": "application/json" });
      const responseBody = JSON.parse(res.end.mock.calls[0][0]);
      expect(responseBody.error.type).toBe("upstream_error");
    });

    it("handles string error", async () => {
      piStream.mockReturnValue(makeEventStream([
        { type: "error", error: "Something went wrong" },
      ]));

      const body = Buffer.from(JSON.stringify({
        messages: [{ role: "user", content: "Hi" }],
      }));

      const usage = await forwardRequest(body, res, { warning: false });

      expect(res.writeHead).toHaveBeenCalledWith(502, { "content-type": "application/json" });
    });
  });

  describe("streaming", () => {
    it("sends SSE format with chunked deltas", async () => {
      piStream.mockReturnValue(makeEventStream([
        { type: "text_delta", delta: "Hi" },
        { type: "done", message: { usage: { input: 5, output: 2 }, model: "gpt-4o" } },
      ]));

      const body = Buffer.from(JSON.stringify({
        model: "gpt-4o",
        stream: true,
        messages: [{ role: "user", content: "Hello" }],
      }));

      const usage = await forwardRequest(body, res, { warning: false });

      expect(res.writeHead).toHaveBeenCalledWith(200, expect.objectContaining({
        "content-type": "text/event-stream",
      }));

      // Should have: text chunk, final chunk (stop + usage), [DONE]
      expect(res.write).toHaveBeenCalledTimes(3);
      // First chunk has content delta
      const firstChunk = JSON.parse(res.write.mock.calls[0][0].replace("data: ", "").trim());
      expect(firstChunk.object).toBe("chat.completion.chunk");
      expect(firstChunk.choices[0].delta.content).toBe("Hi");
      expect(firstChunk.choices[0].finish_reason).toBeNull();

      // Final chunk has finish_reason and usage
      const finalChunk = JSON.parse(res.write.mock.calls[1][0].replace("data: ", "").trim());
      expect(finalChunk.choices[0].finish_reason).toBe("stop");
      expect(finalChunk.usage.total_tokens).toBe(7);

      // [DONE] sentinel
      expect(res.write.mock.calls[2][0]).toBe("data: [DONE]\n\n");

      expect(usage.prompt_tokens).toBe(5);
      expect(usage.completion_tokens).toBe(2);
    });

    it("handles stream error gracefully", async () => {
      piStream.mockReturnValue(makeEventStream([
        { type: "text_delta", delta: "partial" },
        { type: "error", error: "connection reset" },
      ]));

      const body = Buffer.from(JSON.stringify({
        stream: true,
        messages: [{ role: "user", content: "Hi" }],
      }));

      const usage = await forwardRequest(body, res, { warning: false });
      // Should still send a chunk with finish_reason stop on error
      const allWrites = res.write.mock.calls.map((c) => c[0]);
      const hasDone = allWrites.some((w) => w.includes("[DONE]"));
      expect(hasDone).toBe(true);
    });
  });

  describe("warning header", () => {
    it("sets X-Token-Warning header when warning is true", async () => {
      piStream.mockReturnValue(makeEventStream([
        { type: "text_delta", delta: "ok" },
        { type: "done", message: { usage: { input: 1, output: 1 } } },
      ]));

      const body = Buffer.from(JSON.stringify({
        messages: [{ role: "user", content: "Hi" }],
      }));

      await forwardRequest(body, res, { warning: true });
      expect(res.setHeader).toHaveBeenCalledWith("X-Token-Warning", "90%");
    });

    it("does not set warning header when warning is false", async () => {
      piStream.mockReturnValue(makeEventStream([
        { type: "text_delta", delta: "ok" },
        { type: "done", message: { usage: { input: 1, output: 1 } } },
      ]));

      const body = Buffer.from(JSON.stringify({
        messages: [{ role: "user", content: "Hi" }],
      }));

      await forwardRequest(body, res, { warning: false });
      expect(res.setHeader).not.toHaveBeenCalled();
    });
  });

  describe("OpenAI to pi-ai context conversion", () => {
    it("converts system messages to systemPrompt", async () => {
      piStream.mockReturnValue(makeEventStream([
        { type: "text_delta", delta: "ok" },
        { type: "done", message: { usage: { input: 1, output: 1 } } },
      ]));

      const body = Buffer.from(JSON.stringify({
        messages: [
          { role: "system", content: "You are helpful." },
          { role: "user", content: "Hi" },
        ],
      }));

      await forwardRequest(body, res, { warning: false });

      const [model, context] = piStream.mock.calls[0];
      expect(context.systemPrompt).toBe("You are helpful.");
      expect(context.messages).toHaveLength(1);
      expect(context.messages[0].role).toBe("user");
    });

    it("combines multiple system messages", async () => {
      piStream.mockReturnValue(makeEventStream([
        { type: "done", message: { usage: { input: 1, output: 1 } } },
      ]));

      const body = Buffer.from(JSON.stringify({
        messages: [
          { role: "system", content: "First rule." },
          { role: "system", content: "Second rule." },
          { role: "user", content: "Hi" },
        ],
      }));

      await forwardRequest(body, res, { warning: false });

      const [, context] = piStream.mock.calls[0];
      expect(context.systemPrompt).toBe("First rule.\nSecond rule.");
    });

    it("converts image_url content parts", async () => {
      piStream.mockReturnValue(makeEventStream([
        { type: "done", message: { usage: { input: 1, output: 1 } } },
      ]));

      const body = Buffer.from(JSON.stringify({
        messages: [{
          role: "user",
          content: [
            { type: "text", text: "What is this?" },
            { type: "image_url", image_url: { url: "https://example.com/img.png" } },
          ],
        }],
      }));

      await forwardRequest(body, res, { warning: false });

      const [, context] = piStream.mock.calls[0];
      expect(context.messages[0].content).toEqual([
        { type: "text", text: "What is this?" },
        { type: "image", url: "https://example.com/img.png" },
      ]);
    });

    it("handles string content in user messages", async () => {
      piStream.mockReturnValue(makeEventStream([
        { type: "done", message: { usage: { input: 1, output: 1 } } },
      ]));

      const body = Buffer.from(JSON.stringify({
        messages: [{ role: "user", content: "Hello world" }],
      }));

      await forwardRequest(body, res, { warning: false });

      const [, context] = piStream.mock.calls[0];
      expect(context.messages[0].content).toEqual([{ type: "text", text: "Hello world" }]);
    });

    it("converts OpenAI tools to pi-ai tools", async () => {
      piStream.mockReturnValue(makeEventStream([
        { type: "done", message: { usage: { input: 1, output: 1 } } },
      ]));

      const body = Buffer.from(JSON.stringify({
        messages: [{ role: "user", content: "List files" }],
        tools: [{
          type: "function",
          function: {
            name: "list_files",
            description: "List files in a directory",
            parameters: { type: "object", properties: { path: { type: "string" } } },
          },
        }],
      }));

      await forwardRequest(body, res, { warning: false });

      const [, context] = piStream.mock.calls[0];
      expect(context.tools).toHaveLength(1);
      expect(context.tools[0].name).toBe("list_files");
      expect(context.tools[0].description).toBe("List files in a directory");
      expect(context.tools[0].parameters).toEqual({ type: "object", properties: { path: { type: "string" } } });
    });

    it("converts assistant tool_calls to pi-ai ToolCall content", async () => {
      piStream.mockReturnValue(makeEventStream([
        { type: "done", message: { usage: { input: 1, output: 1 } } },
      ]));

      const body = Buffer.from(JSON.stringify({
        messages: [
          { role: "user", content: "List files" },
          {
            role: "assistant",
            content: null,
            tool_calls: [{
              id: "call_123",
              type: "function",
              function: { name: "list_files", arguments: '{"path":"/tmp"}' },
            }],
          },
          { role: "tool", tool_call_id: "call_123", name: "list_files", content: "file1.txt\nfile2.txt" },
          { role: "user", content: "Great, now delete file1" },
        ],
      }));

      await forwardRequest(body, res, { warning: false });

      const [, context] = piStream.mock.calls[0];
      // assistant message with tool call
      expect(context.messages[1].role).toBe("assistant");
      expect(context.messages[1].content).toEqual([{
        type: "toolCall",
        id: "call_123",
        name: "list_files",
        arguments: { path: "/tmp" },
      }]);
      // tool result message
      expect(context.messages[2].role).toBe("toolResult");
      expect(context.messages[2].toolCallId).toBe("call_123");
      expect(context.messages[2].toolName).toBe("list_files");
      expect(context.messages[2].content).toEqual([{ type: "text", text: "file1.txt\nfile2.txt" }]);
    });
  });

  describe("tool call responses", () => {
    it("returns tool_calls in non-streaming response", async () => {
      piStream.mockReturnValue(makeEventStream([
        { type: "done", reason: "toolUse", message: {
          content: [
            { type: "text", text: "I'll list the files." },
            { type: "toolCall", id: "call_abc", name: "list_files", arguments: { path: "/tmp" } },
          ],
          usage: { input: 10, output: 20 },
          model: "k2p5",
        }},
      ]));

      const body = Buffer.from(JSON.stringify({
        messages: [{ role: "user", content: "List files" }],
        tools: [{ type: "function", function: { name: "list_files", description: "List files", parameters: {} } }],
      }));

      const usage = await forwardRequest(body, res, { warning: false });

      const responseBody = JSON.parse(res.end.mock.calls[0][0]);
      expect(responseBody.choices[0].finish_reason).toBe("tool_calls");
      expect(responseBody.choices[0].message.content).toBe("I'll list the files.");
      expect(responseBody.choices[0].message.tool_calls).toEqual([{
        id: "call_abc",
        type: "function",
        function: { name: "list_files", arguments: '{"path":"/tmp"}' },
      }]);
    });

    it("streams tool_calls in SSE format", async () => {
      const partialWithStart = {
        content: [
          { type: "toolCall", id: "call_xyz", name: "read_file", arguments: {} },
        ],
      };

      piStream.mockReturnValue(makeEventStream([
        { type: "toolcall_start", contentIndex: 0, partial: partialWithStart },
        { type: "toolcall_delta", contentIndex: 0, delta: '{"path":' },
        { type: "toolcall_delta", contentIndex: 0, delta: '"/tmp/f.txt"}' },
        { type: "done", reason: "toolUse", message: {
          content: [{ type: "toolCall", id: "call_xyz", name: "read_file", arguments: { path: "/tmp/f.txt" } }],
          usage: { input: 5, output: 10 },
          model: "k2p5",
        }},
      ]));

      const body = Buffer.from(JSON.stringify({
        stream: true,
        messages: [{ role: "user", content: "Read file" }],
        tools: [{ type: "function", function: { name: "read_file", description: "Read", parameters: {} } }],
      }));

      await forwardRequest(body, res, { warning: false });

      const chunks = res.write.mock.calls.map((c) => c[0]);

      // First chunk: toolcall_start with id and name
      const startChunk = JSON.parse(chunks[0].replace("data: ", "").trim());
      expect(startChunk.choices[0].delta.tool_calls[0].id).toBe("call_xyz");
      expect(startChunk.choices[0].delta.tool_calls[0].function.name).toBe("read_file");

      // Middle chunks: argument deltas
      const delta1 = JSON.parse(chunks[1].replace("data: ", "").trim());
      expect(delta1.choices[0].delta.tool_calls[0].function.arguments).toBe('{"path":');

      const delta2 = JSON.parse(chunks[2].replace("data: ", "").trim());
      expect(delta2.choices[0].delta.tool_calls[0].function.arguments).toBe('"/tmp/f.txt"}');

      // Final chunk: finish_reason = tool_calls
      const finalChunk = JSON.parse(chunks[3].replace("data: ", "").trim());
      expect(finalChunk.choices[0].finish_reason).toBe("tool_calls");

      // [DONE] sentinel
      expect(chunks[4]).toBe("data: [DONE]\n\n");
    });
  });
});
