import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        primary: { DEFAULT: "#0E8A5F", deep: "#0A6E4A", soft: "#E5F3EC", contrast: "#FFFFFF" },
        secondary: { DEFAULT: "#C8922B", soft: "#F8EFD9", contrast: "#FFFFFF" }, // Fortune Gold — sparingly for "lucky"/featured
        canvas: "#FAF8F3",
        surface: "#FFFFFF",
        "surface-2": "#F1ECE3",
        ink: { DEFAULT: "#1B2320", 2: "#4C5550", 3: "#6B736E" },
        border: { DEFAULT: "#E4DED3", strong: "#D6CEC0" },
        success: { DEFAULT: "#1F9D57", soft: "#E5F3EC", contrast: "#FFFFFF" },
        warning: { DEFAULT: "#B7791F", soft: "#FBF1DD", contrast: "#FFFFFF" },
        error: { DEFAULT: "#C0392B", soft: "#FAE9E6", contrast: "#FFFFFF" },
        info: { DEFAULT: "#2563EB", soft: "#E8EEFB", contrast: "#FFFFFF" },
      },
      borderRadius: { sm: "6px", md: "10px", lg: "16px" },
      boxShadow: {
        sm: "0 1px 2px rgba(27,35,32,0.06)",
        md: "0 4px 12px rgba(27,35,32,0.08)",
        lg: "0 12px 32px rgba(27,35,32,0.12)",
      },
      fontFamily: { sans: ["Inter", "system-ui", "-apple-system", "Segoe UI", "Roboto", "sans-serif"] },
    },
  },
  plugins: [],
} satisfies Config;
