/** Footer link. Only an https GitHub URL is accepted, so a bad value cannot become a script URL. */
export function githubRepoUrl(): string | null {
  const raw = process.env.NEXT_PUBLIC_GITHUB_REPO_URL?.trim();
  if (!raw) return null;
  try {
    const url = new URL(raw);
    const host = url.hostname.toLowerCase();
    if (url.protocol !== "https:") return null;
    if (host !== "github.com" && host !== "www.github.com") return null;
    return url.toString();
  } catch {
    return null;
  }
}
