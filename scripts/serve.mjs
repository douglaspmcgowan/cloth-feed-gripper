// Static server rooted at public/, the same tree Vercel serves (vercel.json outputDirectory).
// Handles Range requests so the films can seek, and serves nothing outside public/.
//
//   node scripts/serve.mjs [port]      default 4173
import { createServer } from "node:http";
import { createReadStream, statSync } from "node:fs";
import { extname, join, normalize, resolve, sep } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(fileURLToPath(new URL("../public", import.meta.url)));
const port = Number(process.argv[2] || process.env.PORT || 4173);

const TYPES = {
  ".html": "text/html; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".svg": "image/svg+xml",
  ".txt": "text/plain; charset=utf-8",
  ".mp4": "video/mp4",
  ".webp": "image/webp",
  ".jpg": "image/jpeg",
  ".png": "image/png",
};

function locate(urlPath) {
  const decoded = decodeURIComponent(urlPath.split("?")[0]);
  const full = normalize(join(root, decoded));
  if (full !== root && !full.startsWith(root + sep)) return null;
  let st;
  try {
    st = statSync(full);
  } catch {
    // cleanUrls: /name serves name.html
    try {
      const alt = full + ".html";
      return { file: alt, st: statSync(alt) };
    } catch {
      return null;
    }
  }
  if (st.isDirectory()) {
    const idx = join(full, "index.html");
    try {
      return { file: idx, st: statSync(idx) };
    } catch {
      return null;
    }
  }
  return { file: full, st };
}

const server = createServer((req, res) => {
  const hit = req.method === "GET" || req.method === "HEAD" ? locate(req.url) : null;
  if (!hit) {
    res.writeHead(404, { "content-type": "text/plain; charset=utf-8" });
    res.end("Not found");
    return;
  }
  const { file, st } = hit;
  const type = TYPES[extname(file)] || "application/octet-stream";
  const range = /^bytes=(\d*)-(\d*)$/.exec(req.headers.range || "");
  const headers = { "content-type": type, "accept-ranges": "bytes", "cache-control": "no-cache" };
  if (range && (range[1] || range[2])) {
    let start = range[1] ? Number(range[1]) : st.size - Number(range[2]);
    let end = range[1] && range[2] ? Number(range[2]) : st.size - 1;
    end = Math.min(end, st.size - 1);
    if (start > end || start >= st.size) {
      res.writeHead(416, { "content-range": `bytes */${st.size}` });
      res.end();
      return;
    }
    res.writeHead(206, { ...headers, "content-range": `bytes ${start}-${end}/${st.size}`, "content-length": end - start + 1 });
    if (req.method === "HEAD") return res.end();
    createReadStream(file, { start, end }).pipe(res);
    return;
  }
  res.writeHead(200, { ...headers, "content-length": st.size });
  if (req.method === "HEAD") return res.end();
  createReadStream(file).pipe(res);
});

server.listen(port, "127.0.0.1", () => console.log(`serving ${root} at http://127.0.0.1:${port}/`));
