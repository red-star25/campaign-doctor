import { afterEach, describe, expect, it, vi } from "vitest";
import { apiBaseUrl, compareScenario, fetchScenarios } from "@/lib/api";
import { githubRepoUrl } from "@/lib/site";
import { ApiError } from "@/lib/errors";
import { makeComparison } from "./fixtures";

describe("api client", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.unstubAllEnvs();
  });

  it("posts only the provider condition", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => makeComparison("reply_visible", "CANCEL"),
    });
    vi.stubGlobal("fetch", fetchMock);

    await compareScenario("delayed_reply", "reply_visible");

    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/scenarios/delayed_reply/compare",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ provider_condition: "reply_visible" }),
      }),
    );
  });

  it("reports an unreachable API without a stack trace", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));
    try {
      await fetchScenarios();
      expect.fail("expected the request to fail");
    } catch (error) {
      expect(error).toBeInstanceOf(ApiError);
      const apiError = error as ApiError;
      expect(apiError.unreachable).toBe(true);
      expect(apiError.message).toMatch(/could not reach the API/);
      expect(apiError.message).not.toMatch(/Traceback|\/Users\//);
    }
  });

  it("does not call localhost when a production build omitted the API address", async () => {
    vi.stubEnv("NODE_ENV", "production");
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "");
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    expect(apiBaseUrl()).toBeNull();
    await expect(fetchScenarios()).rejects.toThrow(/NEXT_PUBLIC_API_BASE_URL/);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("uses a configured API origin and only an https GitHub link", () => {
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "https://api.example.com/");
    vi.stubEnv("NEXT_PUBLIC_GITHUB_REPO_URL", "https://github.com/example/cardinal");
    expect(apiBaseUrl()).toBe("https://api.example.com");
    expect(githubRepoUrl()).toBe("https://github.com/example/cardinal");

    vi.stubEnv("NEXT_PUBLIC_GITHUB_REPO_URL", "javascript:alert(1)");
    expect(githubRepoUrl()).toBeNull();
  });
});
