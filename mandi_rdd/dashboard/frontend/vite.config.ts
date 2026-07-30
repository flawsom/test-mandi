import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  build: {
    outDir: "dist",
    // Streamlit loads the bundle from the declare_component path.
    // Relative asset paths work when the dist/ is committed to the repo.
    base: "./",
    // NO manualChunks: the bundle is injected inline via
    // theme.py's inject_webgl_hero() as <script type="module">.
    // Inline modules can't use relative imports (no base URL to
    // resolve against), so the entire WebGLHero + three/fiber/drei
    // must be self-contained in one chunk.
    // (FlipBoard is a separate iframe component with its own entry.)
  },
});
