import { mkdir, readFile, writeFile } from "node:fs/promises";

const source = new URL("../src/danish-news-card.js", import.meta.url);
const destinations = [
  new URL("../dist/danish-news-card.js", import.meta.url),
  new URL("../custom_components/danish_news/www/danish-news-card.js", import.meta.url),
  new URL("../examples/danish-news-demo/danish-news-card.js", import.meta.url)
];
const sourceCode = await readFile(source, "utf8");
const banner = [
  "/*",
  " * Danish News Card",
  " * Home Assistant Lovelace custom card bundled with custom_components/danish_news",
  " */",
  ""
].join("\n");

await mkdir(new URL("../dist/", import.meta.url), { recursive: true });
await mkdir(new URL("../custom_components/danish_news/www/", import.meta.url), { recursive: true });
await mkdir(new URL("../examples/danish-news-demo/", import.meta.url), { recursive: true });

for (const destination of destinations) {
  await writeFile(destination, `${banner}${sourceCode}`);
  console.log(`Built ${destination.pathname.split("/").slice(-3).join("/")}`);
}
