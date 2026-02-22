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
        { type: "done", message: { usage: { input: 10, output: 5 }, model: "gpt-4o" } },
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
  });
});
