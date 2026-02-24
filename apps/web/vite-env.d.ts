/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_DEV_MODE: string;
  readonly VITE_NANGO_URL: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
